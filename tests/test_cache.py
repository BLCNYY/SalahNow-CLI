from __future__ import annotations

from pathlib import Path

from salahnow_cli import cache
from salahnow_cli.models import Location, PrayerTimes


def test_cache_roundtrip(tmp_path: Path, monkeypatch) -> None:
    cache_dir = tmp_path / "cache"
    cache_path = cache_dir / "prayer_cache.json"

    monkeypatch.setattr(cache, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(cache, "CACHE_PATH", cache_path)

    location = Location(
        city="Istanbul",
        country="Türkiye",
        countryCode="TR",
        lat=41.0082,
        lon=28.9784,
        diyanetIlceId="9541",
    )
    times = PrayerTimes(
        Fajr="06:22",
        Sunrise="07:48",
        Dhuhr="13:23",
        Asr="16:19",
        Maghrib="18:48",
        Isha="20:08",
    )

    cache.set_cached_bundle(
        location=location,
        source="diyanet",
        times=times,
        tomorrow_fajr="06:21",
        time_zone="Europe/Istanbul",
    )

    fresh = cache.get_fresh_cached_bundle(location, "diyanet")
    assert fresh is not None
    assert fresh.times.Isha == "20:08"
    assert fresh.tomorrow_fajr == "06:21"
