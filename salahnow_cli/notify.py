from __future__ import annotations

import json
import platform
import shutil
import subprocess
import time
from typing import Callable

from rich.console import Console

from .models import Location, PrayerSource, TimeFormat
from .output import format_time_for_display
from .prayer_api import PrayerApiError, fetch_prayer_bundle
from .prayer_logic import get_current_prayer_info


def send_system_notification(title: str, message: str) -> bool:
    system = platform.system()

    if system == "Darwin":
        script = (
            f"display notification {json.dumps(message)} "
            f"with title {json.dumps(title)}"
        )
        result = subprocess.run(
            ["osascript", "-e", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0

    if system == "Linux" and shutil.which("notify-send"):
        result = subprocess.run(
            ["notify-send", title, message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0

    return False


def run_notify_daemon(
    console: Console,
    location: Location,
    source: PrayerSource,
    time_format: TimeFormat,
    on_tick: Callable[[], None] | None = None,
) -> None:
    console.print("[bold green]Notification daemon started.[/bold green] Press Ctrl+C to stop.")

    while True:
        if on_tick:
            on_tick()

        try:
            bundle = fetch_prayer_bundle(location, source)
            info = get_current_prayer_info(
                bundle.times,
                bundle.tomorrow_fajr,
                bundle.time_zone,
            )
        except PrayerApiError as exc:
            console.print(f"[red]Prayer API error:[/red] {exc}. Retrying in 60 seconds.")
            time.sleep(60)
            continue
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]Unexpected error:[/red] {exc}. Retrying in 60 seconds.")
            time.sleep(60)
            continue

        wait_seconds = max(1, info.time_until_next_ms // 1000)
        next_time_display = format_time_for_display(info.next_prayer_time, time_format)
        console.print(
            f"Waiting for [bold green]{info.next_prayer}[/bold green] at {next_time_display} "
            f"({wait_seconds}s)."
        )
        time.sleep(wait_seconds)

        message = f"It's time for {info.next_prayer} ({next_time_display})"
        notified = send_system_notification("SalahNow", message)
        if not notified:
            console.print(f"[yellow]{message}[/yellow]")

        # Short pause so we don't re-trigger instantly due small clock drifts.
        time.sleep(2)
