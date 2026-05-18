from __future__ import annotations

import math
from typing import Any

from sqlalchemy import ColumnElement, func, or_


def like_pattern(term: str) -> str:
    t = term.strip().lower()
    escaped = t.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def apply_text_search(q: Any, term: str | None, *columns) -> Any:
    if not term or not str(term).strip():
        return q
    like = like_pattern(str(term))
    return q.filter(or_(*(func.lower(col).like(like) for col in columns)))


def apply_city_filter(q: Any, column, city: str | None) -> Any:
    if not city or not str(city).strip():
        return q
    return q.filter(func.lower(column) == str(city).strip().lower())


def geo_bbox_clauses(
    lat_col,
    lon_col,
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> tuple[ColumnElement[bool], ...]:
    lat_delta = radius_km / 111.0
    cos_lat = math.cos(math.radians(center_lat))
    lon_delta = radius_km / (111.0 * max(abs(cos_lat), 0.01))
    return (
        lat_col.isnot(None),
        lon_col.isnot(None),
        lat_col >= center_lat - lat_delta,
        lat_col <= center_lat + lat_delta,
        lon_col >= center_lon - lon_delta,
        lon_col <= center_lon + lon_delta,
    )
