from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
import time
from zoneinfo import ZoneInfo

import httpx

from .cache import (
    get_fresh_cached_bundle,
    get_stale_cached_bundle,
    set_cached_bundle,
)
from .location import find_nearest_location_by_country_code
from .models import Location, PrayerSource, PrayerTimes

ALADHAN_BASE_URL = "https://api.aladhan.com/v1"
DIYANET_BASE_URL = "https://ezanvakti.emushaf.net/vakitler"
DIYANET_TIME_ZONE = "Europe/Istanbul"
TURKEY_COUNTRY_CODE = "TR"
MAX_RETRIES = 2
RETRY_BASE_DELAY_SEC = 0.8


class PrayerApiError(RuntimeError):
    pass


@dataclass
class PrayerFetchResult:
    times: PrayerTimes
    tomorrow_fajr: str
    time_zone: str | None
    requested_source: PrayerSource
    resolved_source: PrayerSource


def format_time_to_hhmm(value: str) -> str:
    match = re.search(r"(\d{1,2}):(\d{2})", value)
    if not match:
        return value
    hours = int(match.group(1))
    minutes = int(match.group(2))
    return f"{hours:02}:{minutes:02}"


def _require_time_field(payload: dict[str, object], key: str) -> str:
    raw = payload.get(key)
    if not isinstance(raw, str):
        raise PrayerApiError(f"Missing time field: {key}")

    hhmm = format_time_to_hhmm(raw)
    if not re.fullmatch(r"\d{2}:\d{2}", hhmm):
        raise PrayerApiError(f"Invalid time format for {key}")
    return hhmm


def _get_with_retries(url: str, headers: dict[str, str], error_message: str) -> httpx.Response:
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=20.0, headers=headers) as client:
                response = client.get(url)

            if response.status_code >= 500 and attempt < MAX_RETRIES:
                time.sleep(RETRY_BASE_DELAY_SEC * (attempt + 1))
                continue

            return response
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BASE_DELAY_SEC * (attempt + 1))
                continue
            break

    raise PrayerApiError(error_message) from last_error


def is_turkiye_location(location: Location) -> bool:
    if location.countryCode.upper() == TURKEY_COUNTRY_CODE:
        return True
    country = location.country.strip().lower()
    return country in {"türkiye", "turkiye"}


def get_diyanet_ilce_id(location: Location) -> str | None:
    if location.diyanetIlceId:
        return location.diyanetIlceId
    if not is_turkiye_location(location):
        return None
    nearest = find_nearest_location_by_country_code(
        location.lat,
        location.lon,
        TURKEY_COUNTRY_CODE,
    )
    return nearest.diyanetIlceId if nearest else None


def resolve_prayer_source(location: Location, source: PrayerSource) -> PrayerSource:
    return source if is_turkiye_location(location) else "mwl"


def _parse_diyanet_date_parts(value: str) -> tuple[int, int, int] | None:
    matches = re.findall(r"\d+", value)
    if len(matches) < 3:
        return None

    day, month, year = (int(matches[0]), int(matches[1]), int(matches[2]))
    if not day or not month or not year:
        return None

    return year, month, day


def _get_timezone_date_parts(moment: datetime, time_zone: str) -> tuple[int, int, int]:
    zoned = moment.astimezone(ZoneInfo(time_zone))
    return zoned.year, zoned.month, zoned.day


def _find_diyanet_prayer_times(
    data: list[dict[str, str]],
    target_date: datetime,
) -> dict[str, str] | None:
    target_parts = _get_timezone_date_parts(target_date, DIYANET_TIME_ZONE)

    for entry in data:
        parsed = _parse_diyanet_date_parts(entry.get("MiladiTarihKisa", ""))
        if parsed == target_parts:
            return entry
    return None


def _fetch_from_diyanet(ilce_id: str) -> list[dict[str, str]]:
    url = f"{DIYANET_BASE_URL}/{ilce_id}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "SalahNow",
    }

    response = _get_with_retries(url, headers, "Failed to fetch prayer times from Diyanet")

    if response.status_code >= 400:
        raise PrayerApiError("Failed to fetch prayer times from Diyanet")

    text = response.text.lstrip("\ufeff")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PrayerApiError("Invalid response from Diyanet") from exc

    if not isinstance(payload, list):
        raise PrayerApiError("Unexpected Diyanet response")

    return payload


def _fetch_prayer_times_from_diyanet(ilce_id: str) -> PrayerTimes:
    data = _fetch_from_diyanet(ilce_id)
    today = datetime.now(ZoneInfo(DIYANET_TIME_ZONE))
    today_times = _find_diyanet_prayer_times(data, today)

    if not today_times:
        raise PrayerApiError("Could not find today's prayer times")

    return PrayerTimes(
        Fajr=_require_time_field(today_times, "Imsak"),
        Sunrise=_require_time_field(today_times, "Gunes"),
        Dhuhr=_require_time_field(today_times, "Ogle"),
        Asr=_require_time_field(today_times, "Ikindi"),
        Maghrib=_require_time_field(today_times, "Aksam"),
        Isha=_require_time_field(today_times, "Yatsi"),
    )


def _fetch_tomorrow_fajr_from_diyanet(ilce_id: str) -> str:
    data = _fetch_from_diyanet(ilce_id)
    tomorrow = datetime.now(ZoneInfo(DIYANET_TIME_ZONE)) + timedelta(days=1)
    tomorrow_times = _find_diyanet_prayer_times(data, tomorrow)

    if not tomorrow_times:
        raise PrayerApiError("Could not find tomorrow's prayer times")

    return _require_time_field(tomorrow_times, "Imsak")


def _aladhan_timings_url(timestamp: int, location: Location) -> str:
    return (
        f"{ALADHAN_BASE_URL}/timings/{timestamp}"
        f"?latitude={location.lat}&longitude={location.lon}&method=3&school=1"
    )


def _fetch_prayer_times_from_aladhan(location: Location) -> tuple[PrayerTimes, str | None]:
    timestamp = int(datetime.now().timestamp())
    url = _aladhan_timings_url(timestamp, location)

    response = _get_with_retries(
        url,
        {"User-Agent": "SalahNow CLI"},
        "Failed to fetch prayer times",
    )

    if response.status_code >= 400:
        raise PrayerApiError("Failed to fetch prayer times")

    try:
        payload = response.json()
    except ValueError as exc:
        raise PrayerApiError("Invalid response from AlAdhan") from exc

    data = payload.get("data", {})
    timings = data.get("timings", {})
    if not isinstance(timings, dict):
        raise PrayerApiError("Unexpected response format from AlAdhan")

    return (
        PrayerTimes(
            Fajr=_require_time_field(timings, "Fajr"),
            Sunrise=_require_time_field(timings, "Sunrise"),
            Dhuhr=_require_time_field(timings, "Dhuhr"),
            Asr=_require_time_field(timings, "Asr"),
            Maghrib=_require_time_field(timings, "Maghrib"),
            Isha=_require_time_field(timings, "Isha"),
        ),
        data.get("meta", {}).get("timezone"),
    )


def _fetch_tomorrow_fajr_from_aladhan(location: Location) -> str:
    tomorrow = datetime.now() + timedelta(days=1)
    timestamp = int(tomorrow.timestamp())
    url = _aladhan_timings_url(timestamp, location)

    response = _get_with_retries(
        url,
        {"User-Agent": "SalahNow CLI"},
        "Failed to fetch tomorrow's prayer times",
    )

    if response.status_code >= 400:
        raise PrayerApiError("Failed to fetch tomorrow's prayer times")

    try:
        payload = response.json()
    except ValueError as exc:
        raise PrayerApiError("Invalid response from AlAdhan") from exc

    data = payload.get("data", {})
    timings = data.get("timings", {})
    if not isinstance(timings, dict):
        raise PrayerApiError("Unexpected response format from AlAdhan")
    return _require_time_field(timings, "Fajr")


def fetch_prayer_bundle(
    location: Location,
    source: PrayerSource = "diyanet",
) -> PrayerFetchResult:
    resolved_source = resolve_prayer_source(location, source)
    fresh_cached = get_fresh_cached_bundle(location, resolved_source)
    if fresh_cached:
        return PrayerFetchResult(
            times=fresh_cached.times,
            tomorrow_fajr=fresh_cached.tomorrow_fajr,
            time_zone=fresh_cached.time_zone,
            requested_source=source,
            resolved_source=resolved_source,
        )

    try:
        if resolved_source == "diyanet":
            ilce_id = get_diyanet_ilce_id(location)
            if not ilce_id:
                raise PrayerApiError("Failed to resolve Diyanet location")

            times = _fetch_prayer_times_from_diyanet(ilce_id)
            tomorrow_fajr = _fetch_tomorrow_fajr_from_diyanet(ilce_id)
            set_cached_bundle(
                location=location,
                source=resolved_source,
                times=times,
                tomorrow_fajr=tomorrow_fajr,
                time_zone=DIYANET_TIME_ZONE,
            )
            return PrayerFetchResult(
                times=times,
                tomorrow_fajr=tomorrow_fajr,
                time_zone=DIYANET_TIME_ZONE,
                requested_source=source,
                resolved_source=resolved_source,
            )

        times, time_zone = _fetch_prayer_times_from_aladhan(location)
        tomorrow_fajr = _fetch_tomorrow_fajr_from_aladhan(location)
        set_cached_bundle(
            location=location,
            source=resolved_source,
            times=times,
            tomorrow_fajr=tomorrow_fajr,
            time_zone=time_zone,
        )
        return PrayerFetchResult(
            times=times,
            tomorrow_fajr=tomorrow_fajr,
            time_zone=time_zone,
            requested_source=source,
            resolved_source=resolved_source,
        )
    except PrayerApiError:
        stale_cached = get_stale_cached_bundle(location, resolved_source)
        if stale_cached:
            return PrayerFetchResult(
                times=stale_cached.times,
                tomorrow_fajr=stale_cached.tomorrow_fajr,
                time_zone=stale_cached.time_zone,
                requested_source=source,
                resolved_source=resolved_source,
            )
        raise
