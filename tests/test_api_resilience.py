from __future__ import annotations

from salahnow_cli.cache import CachedPrayerBundle
from salahnow_cli.models import Location, PrayerTimes
from salahnow_cli.prayer_api import PrayerApiError, fetch_prayer_bundle, format_time_to_hhmm


def _sample_location_tr() -> Location:
    return Location(
        city="Istanbul",
        country="Türkiye",
        countryCode="TR",
        lat=41.0082,
        lon=28.9784,
        diyanetIlceId="9541",
    )


def _sample_times() -> PrayerTimes:
    return PrayerTimes(
        Fajr="06:22",
        Sunrise="07:48",
        Dhuhr="13:23",
        Asr="16:19",
        Maghrib="18:48",
        Isha="20:08",
    )


def _sample_cached_bundle() -> CachedPrayerBundle:
    return CachedPrayerBundle(
        times=_sample_times(),
        tomorrow_fajr="06:21",
        time_zone="Europe/Istanbul",
        date="2099-01-01",
        fetched_at="2099-01-01T00:00:00+00:00",
    )


def test_format_time_to_hhmm_extracts_value() -> None:
    assert format_time_to_hhmm("5:07 (+03)") == "05:07"


def test_fetch_prayer_bundle_uses_fresh_cache(monkeypatch) -> None:
    monkeypatch.setattr(
        "salahnow_cli.prayer_api.get_fresh_cached_bundle",
        lambda location, source: _sample_cached_bundle(),
    )
    monkeypatch.setattr(
        "salahnow_cli.prayer_api._fetch_prayer_times_from_diyanet",
        lambda ilce_id: (_ for _ in ()).throw(AssertionError("network should not be called")),
    )

    bundle = fetch_prayer_bundle(_sample_location_tr(), "diyanet")

    assert bundle.resolved_source == "diyanet"
    assert bundle.times.Fajr == "06:22"
    assert bundle.tomorrow_fajr == "06:21"


def test_fetch_prayer_bundle_falls_back_to_stale_cache(monkeypatch) -> None:
    monkeypatch.setattr("salahnow_cli.prayer_api.get_fresh_cached_bundle", lambda *_: None)
    monkeypatch.setattr(
        "salahnow_cli.prayer_api.get_stale_cached_bundle",
        lambda *_: _sample_cached_bundle(),
    )

    def _boom(*_args, **_kwargs):
        raise PrayerApiError("upstream down")

    monkeypatch.setattr("salahnow_cli.prayer_api._fetch_prayer_times_from_diyanet", _boom)

    bundle = fetch_prayer_bundle(_sample_location_tr(), "diyanet")

    assert bundle.times.Maghrib == "18:48"
    assert bundle.tomorrow_fajr == "06:21"
