from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

PrayerSource = Literal["diyanet", "mwl"]
TimeFormat = Literal["12h", "24h"]
PrayerName = Literal["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]

PRAYER_NAMES: tuple[PrayerName, ...] = (
    "Fajr",
    "Sunrise",
    "Dhuhr",
    "Asr",
    "Maghrib",
    "Isha",
)


@dataclass
class Location:
    city: str
    country: str
    countryCode: str
    lat: float
    lon: float
    addressLabel: str | None = None
    diyanetIlceId: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Location":
        return cls(
            city=str(data["city"]),
            country=str(data["country"]),
            countryCode=str(data["countryCode"]),
            lat=float(data["lat"]),
            lon=float(data["lon"]),
            addressLabel=data.get("addressLabel"),
            diyanetIlceId=data.get("diyanetIlceId"),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "city": self.city,
            "country": self.country,
            "countryCode": self.countryCode,
            "lat": self.lat,
            "lon": self.lon,
        }
        if self.addressLabel:
            payload["addressLabel"] = self.addressLabel
        if self.diyanetIlceId:
            payload["diyanetIlceId"] = self.diyanetIlceId
        return payload


@dataclass
class PrayerTimes:
    Fajr: str
    Sunrise: str
    Dhuhr: str
    Asr: str
    Maghrib: str
    Isha: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PrayerTimes":
        return cls(
            Fajr=str(data["Fajr"]),
            Sunrise=str(data["Sunrise"]),
            Dhuhr=str(data["Dhuhr"]),
            Asr=str(data["Asr"]),
            Maghrib=str(data["Maghrib"]),
            Isha=str(data["Isha"]),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "Fajr": self.Fajr,
            "Sunrise": self.Sunrise,
            "Dhuhr": self.Dhuhr,
            "Asr": self.Asr,
            "Maghrib": self.Maghrib,
            "Isha": self.Isha,
        }

    def get(self, prayer: PrayerName) -> str:
        return getattr(self, prayer)
