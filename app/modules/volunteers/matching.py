from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from app.core.geo import haversine_km
from app.core.list_query import cities_match_for_volunteer
from app.models.help_request import HelpRequest

DEFAULT_RADIUS_KM = 50
MIN_FEED_SCORE = 12.0


@dataclass(frozen=True)
class VolunteerMatchContext:
    competency_slugs: frozenset[str]
    latitude: float | None
    longitude: float | None
    travel_radius_km: int | None
    location_city: str | None
    is_available: bool
    accepts_night_urgency: bool
    completed_help_types: frozenset[str]
    completed_org_ids: frozenset[int]
    has_weekly_schedule: bool


@dataclass(frozen=True)
class ScoredVolunteerTask:
    request: HelpRequest
    match_score: float
    match_reasons: tuple[str, ...]
    distance_km: float | None
    required_competencies: tuple[str, ...]


def request_required_competencies(req: HelpRequest) -> set[str]:
    slugs: set[str] = set()
    ht = (req.help_type or "").strip().lower()
    if ht:
        slugs.add(ht)
    raw = req.volunteer_competencies_json
    if not raw:
        return slugs
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return slugs
    if not isinstance(data, list):
        return slugs
    for item in data:
        token = str(item).strip().lower()
        if token:
            slugs.add(token)
    return slugs


def _distance_km(ctx: VolunteerMatchContext, req: HelpRequest) -> float | None:
    if ctx.latitude is None or ctx.longitude is None:
        return None
    if req.latitude is None or req.longitude is None:
        return None
    return haversine_km(ctx.latitude, ctx.longitude, float(req.latitude), float(req.longitude))


def _location_score(ctx: VolunteerMatchContext, req: HelpRequest, dist: float | None) -> tuple[float, list[str]]:
    reasons: list[str] = []
    radius = float(ctx.travel_radius_km if ctx.travel_radius_km is not None else DEFAULT_RADIUS_KM)

    if dist is not None:
        if dist <= radius:
            reasons.append("nearby")
            return max(5.0, 28.0 * (1.0 - dist / max(radius, 1.0))), reasons
        volunteer_city = (ctx.location_city or "").strip()
        request_city = (req.city or "").strip()
        if volunteer_city and request_city and cities_match_for_volunteer(volunteer_city, request_city):
            reasons.append("same_city")
            return 14.0, reasons
        return -1.0, []

    volunteer_city = (ctx.location_city or "").strip()
    request_city = (req.city or "").strip()
    if volunteer_city and request_city:
        if cities_match_for_volunteer(volunteer_city, request_city):
            reasons.append("same_city")
            return 18.0, reasons
        return -1.0, []

    if volunteer_city and not request_city:
        reasons.append("location_unknown")
        return 6.0, reasons

    reasons.append("location_unknown")
    return 8.0, reasons


def score_volunteer_task(ctx: VolunteerMatchContext, req: HelpRequest) -> ScoredVolunteerTask | None:
    if not ctx.is_available:
        return None

    required = request_required_competencies(req)
    dist = _distance_km(ctx, req)
    loc_score, loc_reasons = _location_score(ctx, req, dist)
    if loc_score < 0:
        return None

    reasons = list(loc_reasons)
    score = loc_score

    if required:
        if not required.issubset(ctx.competency_slugs):
            return None
        score += 42.0
        reasons.append("skills_match")
    elif ctx.competency_slugs:
        score += 12.0
        reasons.append("general_skills")

    if req.is_urgent:
        score += 22.0
        reasons.append("urgent")
        if req.deadline_at is not None:
            hours_left = (req.deadline_at - datetime.utcnow()).total_seconds() / 3600.0
            if hours_left <= 24:
                score += 14.0
                reasons.append("deadline_soon")
            elif hours_left <= 72:
                score += 7.0
                reasons.append("deadline_week")

    help_type = (req.help_type or "").strip().lower()
    if help_type and help_type in ctx.completed_help_types:
        score += 10.0
        reasons.append("similar_experience")
    if req.organization_id is not None and req.organization_id in ctx.completed_org_ids:
        score += 6.0
        reasons.append("known_organization")
    if ctx.has_weekly_schedule:
        score += 4.0
        reasons.append("availability_set")

    if score < MIN_FEED_SCORE:
        return None

    return ScoredVolunteerTask(
        request=req,
        match_score=round(score, 1),
        match_reasons=tuple(dict.fromkeys(reasons)),
        distance_km=round(dist, 1) if dist is not None else None,
        required_competencies=tuple(sorted(required)),
    )


def sort_scored_tasks(items: list[ScoredVolunteerTask]) -> list[ScoredVolunteerTask]:
    def sort_key(item: ScoredVolunteerTask) -> tuple:
        req = item.request
        urgent_relevant = 1 if req.is_urgent and item.match_score >= MIN_FEED_SCORE else 0
        deadline_ts = req.deadline_at.timestamp() if req.deadline_at else float("inf")
        return (-urgent_relevant, -item.match_score, deadline_ts, -req.created_at.timestamp(), -req.id)

    return sorted(items, key=sort_key)
