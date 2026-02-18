from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .models import Location, PrayerSource, PrayerTimes

CACHE_DIR = Path.home() / ".cache" / "salahnow"
CACHE_PATH = CACHE_DIR / "prayer_cache.json"
DIYANET_TIME_ZONE = "Europe/Istanbul"


@dataclass
class CachedPrayerBundle:
    times: PrayerTimes
    tomorrow_fajr: str
    time_zone: str | None
    date: str
    fetched_at: str


def _cache_key(location: Location, source: PrayerSource) -> str:
    return (
        f"{location.city}-{location.countryCode}-{location.lat:.5f}-{location.lon:.5f}-{source}"
    )


def _safe_read_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}

    try:
        raw = CACHE_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _safe_write_cache(payload: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _date_string_for_zone(time_zone: str | None, source: PrayerSource) -> str:
    if time_zone:
        try:
            return datetime.now(ZoneInfo(time_zone)).date().isoformat()
        except Exception:
            pass

    if source == "diyanet":
        return datetime.now(ZoneInfo(DIYANET_TIME_ZONE)).date().isoformat()

    return datetime.now().date().isoformat()


def _parse_cached_entry(entry: Any) -> CachedPrayerBundle | None:
    if not isinstance(entry, dict):
        return None

    try:
        return CachedPrayerBundle(
            times=PrayerTimes.from_dict(entry["times"]),
            tomorrow_fajr=str(entry["tomorrow_fajr"]),
            time_zone=entry.get("time_zone"),
            date=str(entry["date"]),
            fetched_at=str(entry["fetched_at"]),
        )
    except Exception:
        return None


def get_fresh_cached_bundle(location: Location, source: PrayerSource) -> CachedPrayerBundle | None:
    data = _safe_read_cache()
    key = _cache_key(location, source)
    entry = _parse_cached_entry(data.get(key))
    if not entry:
        return None

    expected_date = _date_string_for_zone(entry.time_zone, source)
    if entry.date == expected_date:
        return entry

    return None


def get_stale_cached_bundle(location: Location, source: PrayerSource) -> CachedPrayerBundle | None:
    data = _safe_read_cache()
    key = _cache_key(location, source)
    return _parse_cached_entry(data.get(key))


def set_cached_bundle(
    location: Location,
    source: PrayerSource,
    times: PrayerTimes,
    tomorrow_fajr: str,
    time_zone: str | None,
) -> None:
    data = _safe_read_cache()
    key = _cache_key(location, source)

    now = datetime.now().astimezone()
    data[key] = {
        "times": times.to_dict(),
        "tomorrow_fajr": tomorrow_fajr,
        "time_zone": time_zone,
        "date": _date_string_for_zone(time_zone, source),
        "fetched_at": now.isoformat(),
    }

    _safe_write_cache(data)
