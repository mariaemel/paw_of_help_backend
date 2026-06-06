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


_CITY_ALIASES: dict[str, str] = {
    "спб": "санкт-петербург",
    "питер": "санкт-петербург",
    "петербург": "санкт-петербург",
    "екб": "екатеринбург",
    "мск": "москва",
}


def normalize_city_token(city: str | None) -> str:
    if not city:
        return ""
    s = str(city).strip().lower().replace("ё", "е")
    for prefix in ("г.", "г ", "город "):
        if s.startswith(prefix):
            s = s[len(prefix) :].strip()
            break
    s = " ".join(s.split())
    return _CITY_ALIASES.get(s, s)


def cities_match_for_volunteer(volunteer_city: str | None, task_city: str | None) -> bool:
    volunteer = normalize_city_token(volunteer_city)
    if not volunteer:
        return True
    task = normalize_city_token(task_city)
    if not task:
        return True
    if volunteer == task:
        return True
    if volunteer in task or task in volunteer:
        return True
    volunteer_parts = [p.strip() for p in volunteer.split(",") if p.strip()] or [volunteer]
    task_parts = [p.strip() for p in task.split(",") if p.strip()] or [task]
    for left in volunteer_parts:
        for right in task_parts:
            if left == right or left in right or right in left:
                return True
    return False


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
