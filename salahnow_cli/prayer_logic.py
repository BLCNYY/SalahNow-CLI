from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .models import PRAYER_NAMES, PrayerName, PrayerTimes


@dataclass
class PrayerTimePoint:
    name: PrayerName
    time: str
    timestamp: datetime


@dataclass
class CurrentPrayerInfo:
    current_prayer: PrayerName | None
    next_prayer: PrayerName
    next_prayer_time: str
    time_until_next_ms: int
    is_after_isha: bool


def get_time_zone_now(time_zone: str | None) -> datetime:
    if time_zone:
        return datetime.now(ZoneInfo(time_zone))
    return datetime.now().astimezone()


def time_string_to_datetime(time_str: str, base_date: datetime) -> datetime:
    hours, minutes = [int(part) for part in time_str.split(":")[:2]]
    return base_date.replace(hour=hours, minute=minutes, second=0, microsecond=0)


def get_prayer_times_array(prayer_times: PrayerTimes, base_date: datetime) -> list[PrayerTimePoint]:
    return [
        PrayerTimePoint(
            name=name,
            time=prayer_times.get(name),
            timestamp=time_string_to_datetime(prayer_times.get(name), base_date),
        )
        for name in PRAYER_NAMES
    ]


def get_current_prayer_info(
    prayer_times: PrayerTimes,
    tomorrow_fajr: str | None = None,
    time_zone: str | None = None,
) -> CurrentPrayerInfo:
    now = get_time_zone_now(time_zone)
    prayers = get_prayer_times_array(prayer_times, now)

    current_prayer: PrayerName | None = None
    next_prayer: PrayerName = "Fajr"
    next_prayer_time = prayer_times.Fajr
    time_until_next = timedelta(0)
    is_after_isha = False

    for i in range(len(prayers) - 1, -1, -1):
        if now >= prayers[i].timestamp:
            current_prayer = prayers[i].name

            if i < len(prayers) - 1:
                next_prayer = prayers[i + 1].name
                next_prayer_time = prayers[i + 1].time
                time_until_next = prayers[i + 1].timestamp - now
            else:
                is_after_isha = True
                next_prayer = "Fajr"
                tomorrow = now + timedelta(days=1)
                next_prayer_time = tomorrow_fajr or prayer_times.Fajr
                tomorrow_fajr_dt = time_string_to_datetime(next_prayer_time, tomorrow)
                time_until_next = tomorrow_fajr_dt - now
            break

    if current_prayer is None:
        current_prayer = "Isha"
        next_prayer = "Fajr"
        next_prayer_time = prayer_times.Fajr
        time_until_next = prayers[0].timestamp - now

    time_until_next_ms = int(time_until_next.total_seconds() * 1000)
    return CurrentPrayerInfo(
        current_prayer=current_prayer,
        next_prayer=next_prayer,
        next_prayer_time=next_prayer_time,
        time_until_next_ms=max(0, time_until_next_ms),
        is_after_isha=is_after_isha,
    )


def format_countdown(ms: int) -> str:
    if ms <= 0:
        return "00:00:00"

    total_seconds = ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}"
