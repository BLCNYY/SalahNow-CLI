from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .location import get_default_location
from .models import Location, PrayerSource, TimeFormat

CONFIG_DIR = Path.home() / ".config" / "salahnow"
CONFIG_PATH = CONFIG_DIR / "config.json"


@dataclass
class Config:
    location: Location
    prayer_source: PrayerSource = "diyanet"
    time_format: TimeFormat = "24h"

    def to_dict(self) -> dict[str, Any]:
        return {
            "location": self.location.to_dict(),
            "prayer_source": self.prayer_source,
            "time_format": self.time_format,
        }


def _sanitize_prayer_source(value: str | None) -> PrayerSource:
    if value in ("diyanet", "mwl"):
        return cast(PrayerSource, value)
    return "diyanet"


def _sanitize_time_format(value: str | None) -> TimeFormat:
    if value in ("12h", "24h"):
        return cast(TimeFormat, value)
    return "24h"


def default_config() -> Config:
    return Config(location=get_default_location())


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        config = default_config()
        save_config(config)
        return config

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        config = default_config()
        save_config(config)
        return config

    location_raw = data.get("location")
    if isinstance(location_raw, dict):
        try:
            location = Location.from_dict(location_raw)
        except Exception:
            location = get_default_location()
    else:
        location = get_default_location()

    return Config(
        location=location,
        prayer_source=_sanitize_prayer_source(data.get("prayer_source")),
        time_format=_sanitize_time_format(data.get("time_format")),
    )


def save_config(config: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config.to_dict(), indent=2) + "\n", encoding="utf-8")
