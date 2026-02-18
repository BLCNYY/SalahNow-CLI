from __future__ import annotations

from datetime import datetime

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import PRAYER_NAMES, Location, PrayerName, PrayerSource, PrayerTimes, TimeFormat
from .prayer_logic import CurrentPrayerInfo, format_countdown, get_time_zone_now, time_string_to_datetime

SOURCE_LABELS: dict[PrayerSource, str] = {
    "diyanet": "Diyanet",
    "mwl": "Muslim World League (AlAdhan)",
}


def format_time_for_display(value: str, time_format: TimeFormat) -> str:
    if time_format == "24h":
        return value

    parsed = datetime.strptime(value, "%H:%M")
    rendered = parsed.strftime("%I:%M %p")
    return rendered[1:] if rendered.startswith("0") else rendered


def _row_style(
    name: PrayerName,
    prayer_time: str,
    now: datetime,
    info: CurrentPrayerInfo,
) -> str | None:
    prayer_dt = time_string_to_datetime(prayer_time, now)
    is_after_isha_tomorrow_fajr = info.is_after_isha and name == "Fajr"

    if name == info.next_prayer and (prayer_dt >= now or is_after_isha_tomorrow_fajr):
        return "bold green"
    if prayer_dt < now and not is_after_isha_tomorrow_fajr:
        return "dim"
    return None


def build_prayer_table(
    prayer_times: PrayerTimes,
    info: CurrentPrayerInfo,
    time_format: TimeFormat,
    time_zone: str | None,
) -> Table:
    now = get_time_zone_now(time_zone)

    table = Table(show_header=True, header_style="bold cyan", expand=False)
    table.add_column("Prayer", style="bold")
    table.add_column("Time", justify="right")

    for name in PRAYER_NAMES:
        raw_time = prayer_times.get(name)
        display_time = format_time_for_display(raw_time, time_format)
        style = _row_style(name, raw_time, now, info)

        prayer_name = name
        if info.is_after_isha and name == "Fajr" and info.next_prayer == "Fajr":
            prayer_name = "Fajr (tomorrow)"

        table.add_row(prayer_name, display_time, style=style)

    return table


def render_today(
    console: Console,
    location: Location,
    prayer_times: PrayerTimes,
    info: CurrentPrayerInfo,
    time_format: TimeFormat,
    time_zone: str | None,
    source: PrayerSource,
) -> None:
    title = Text(f"{location.city}, {location.country}", style="bold")
    subtitle = f"Source: {SOURCE_LABELS[source]}"

    if time_zone:
        now_in_zone = get_time_zone_now(time_zone)
        subtitle += f" | Timezone: {time_zone} | Local there: {now_in_zone.strftime('%H:%M:%S')}"

    table = build_prayer_table(prayer_times, info, time_format, time_zone)
    console.print(Panel(Group(title, subtitle, table), title="SalahNow", border_style="blue"))


def build_next_panel(
    location: Location,
    info: CurrentPrayerInfo,
    time_format: TimeFormat,
    source: PrayerSource,
) -> Panel:
    next_time = format_time_for_display(info.next_prayer_time, time_format)
    countdown = format_countdown(info.time_until_next_ms)

    body = Group(
        Text(f"Location: {location.city}, {location.country}", style="cyan"),
        Text(f"Source: {SOURCE_LABELS[source]}", style="white"),
        Text(f"Next Prayer: {info.next_prayer}", style="bold green"),
        Text(f"At: {next_time}", style="bold"),
        Text(f"Countdown: {countdown}", style="bold yellow"),
    )
    return Panel(body, title="SalahNow Next", border_style="green")
