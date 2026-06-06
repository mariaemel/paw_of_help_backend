from __future__ import annotations

import json
import re
from urllib.parse import quote
from urllib.request import urlopen

from app.core.config import settings


def build_location_query(city: str | None, district: str | None = None) -> str | None:
    city_s = (city or "").strip()
    dist_s = (district or "").strip()
    if city_s and dist_s:
        q = f"{city_s}, {dist_s}"
    elif city_s:
        q = city_s
    elif dist_s:
        q = dist_s
    else:
        return None
    if not re.search(r"россия|russia", q, re.I):
        q = f"{q}, Россия"
    return q


def geocode_location_ru(city: str | None, district: str | None = None) -> tuple[float, float] | None:
    query = build_location_query(city, district)
    key = (settings.yandex_geocoder_api_key or "").strip()
    if not query or not key:
        return None

    url = (
        "https://geocode-maps.yandex.ru/1.x/?"
        f"apikey={quote(key)}&geocode={quote(query)}&format=json&results=1"
    )
    try:
        with urlopen(url, timeout=8) as res:
            data = json.loads(res.read().decode("utf-8"))
    except Exception:
        return None

    pos = (
        data.get("response", {})
        .get("GeoObjectCollection", {})
        .get("featureMember", [{}])[0]
        .get("GeoObject", {})
        .get("Point", {})
        .get("pos")
    )
    if not isinstance(pos, str):
        return None
    parts = pos.split()
    if len(parts) < 2:
        return None
    lon, lat = float(parts[0]), float(parts[1])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def sync_volunteer_profile_coords(profile) -> bool:
    coords = geocode_location_ru(
        getattr(profile, "location_city", None),
        getattr(profile, "location_district", None),
    )
    if coords is None:
        return False
    lat, lon = coords
    if profile.latitude == lat and profile.longitude == lon:
        return False
    profile.latitude = lat
    profile.longitude = lon
    return True
