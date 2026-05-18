from __future__ import annotations

import math
from typing import Callable, TypeVar

T = TypeVar("T")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p = math.pi / 180
    a = (
        0.5
        - math.cos((lat2 - lat1) * p) / 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    )
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def filter_sort_paginate_nearby(
    rows: list[T],
    *,
    center_lat: float,
    center_lon: float,
    radius_km: float,
    get_lat_lon: Callable[[T], tuple[float | None, float | None]],
    sort_key: Callable[[T], tuple],
    offset: int,
    limit: int,
) -> tuple[int, list[T]]:
    kept: list[tuple[T, float]] = []
    for row in rows:
        lat, lon = get_lat_lon(row)
        if lat is None or lon is None:
            continue
        dist = haversine_km(center_lat, center_lon, float(lat), float(lon))
        if dist <= radius_km:
            kept.append((row, dist))
    kept.sort(key=lambda x: (x[1],) + sort_key(x[0]))
    total = len(kept)
    page = [r for r, _ in kept[offset : offset + limit]]
    return total, page
