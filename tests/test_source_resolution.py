from salahnow_cli.models import Location
from salahnow_cli.prayer_api import resolve_prayer_source


def test_non_tr_forces_mwl() -> None:
    loc = Location(
        city="New York",
        country="United States",
        countryCode="US",
        lat=40.7128,
        lon=-74.0060,
    )
    assert resolve_prayer_source(loc, "diyanet") == "mwl"


def test_tr_can_use_diyanet() -> None:
    loc = Location(
        city="Ankara",
        country="Türkiye",
        countryCode="TR",
        lat=39.9334,
        lon=32.8597,
    )
    assert resolve_prayer_source(loc, "diyanet") == "diyanet"
