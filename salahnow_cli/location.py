from __future__ import annotations

import json
import math
from functools import lru_cache
from importlib import resources

import httpx

from .models import Location

IP_GEOLOCATION_URL = "https://ipapi.co/json/"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


@lru_cache(maxsize=1)
def get_locations() -> tuple[Location, ...]:
    path = resources.files("salahnow_cli.data").joinpath("locations.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return tuple(Location.from_dict(item) for item in data)


@lru_cache(maxsize=1)
def get_default_location() -> Location:
    for loc in get_locations():
        if loc.city == "İstanbul":
            return loc
    return get_locations()[0]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def find_nearest_location(lat: float, lon: float) -> Location:
    nearest = get_default_location()
    min_distance = float("inf")

    for loc in get_locations():
        distance = haversine_distance(lat, lon, loc.lat, loc.lon)
        if distance < min_distance:
            min_distance = distance
            nearest = loc

    return nearest


def find_nearest_location_by_country_code(
    lat: float, lon: float, country_code: str
) -> Location | None:
    nearest: Location | None = None
    min_distance = float("inf")

    for loc in get_locations():
        if loc.countryCode != country_code:
            continue

        distance = haversine_distance(lat, lon, loc.lat, loc.lon)
        if distance < min_distance:
            min_distance = distance
            nearest = loc

    return nearest


def get_nearest_locations(lat: float, lon: float, limit: int) -> list[Location]:
    ranked = sorted(
        (
            (haversine_distance(lat, lon, loc.lat, loc.lon), loc)
            for loc in get_locations()
        ),
        key=lambda item: item[0],
    )
    return [loc for _, loc in ranked[:limit]]


def detect_location_from_ip() -> Location:
    with httpx.Client(timeout=10.0, headers={"User-Agent": "SalahNow CLI"}) as client:
        response = client.get(IP_GEOLOCATION_URL)
        response.raise_for_status()
        data = response.json()

    lat = float(data["latitude"])
    lon = float(data["longitude"])
    return find_nearest_location(lat, lon)


def search_locations(query: str, limit: int = 5) -> list[Location]:
    params = {
        "format": "json",
        "limit": str(limit),
        "addressdetails": "1",
        "q": query,
    }

    with httpx.Client(timeout=15.0, headers={"User-Agent": "SalahNow CLI"}) as client:
        response = client.get(NOMINATIM_URL, params=params)
        response.raise_for_status()
        data = response.json()

    locations: list[Location] = []
    for item in data:
        address = item.get("address") or {}
        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("state")
            or "Unknown"
        )
        country = address.get("country") or "Unknown"
        country_code = (address.get("country_code") or "XX").upper()

        locations.append(
            Location(
                city=city,
                country=country,
                countryCode=country_code,
                lat=float(item["lat"]),
                lon=float(item["lon"]),
                addressLabel=item.get("display_name"),
            )
        )

    return locations
