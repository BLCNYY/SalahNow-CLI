from salahnow_cli.models import PrayerTimes
from salahnow_cli.prayer_logic import format_countdown


def test_format_countdown_zero() -> None:
    assert format_countdown(0) == "00:00:00"


def test_format_countdown_values() -> None:
    assert format_countdown(3_661_000) == "01:01:01"


def test_prayer_times_dataclass() -> None:
    pt = PrayerTimes(
        Fajr="05:00",
        Sunrise="06:30",
        Dhuhr="12:15",
        Asr="15:45",
        Maghrib="18:20",
        Isha="19:45",
    )
    assert pt.get("Dhuhr") == "12:15"
