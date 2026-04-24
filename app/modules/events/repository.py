import math

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.organization import Organization
from app.modules.events.schemas import EventFilterParams


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p = math.pi / 180
    a = (
        0.5
        - math.cos((lat2 - lat1) * p) / 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    )
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


class EventRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_catalogs(self) -> list[str]:
        return [
            row[0]
            for row in self.db.query(Event.city).distinct().order_by(Event.city.asc()).all()
            if row[0]
        ]

    def get_event(self, event_id: int) -> tuple[Event, Organization | None] | None:
        return (
            self.db.query(Event, Organization)
            .outerjoin(Organization, Organization.id == Event.organization_id)
            .filter(Event.id == event_id, Event.is_published.is_(True), Event.is_archived.is_(False))
            .first()
        )

    def get_event_for_owner(self, event_id: int) -> tuple[Event, Organization | None] | None:
        return (
            self.db.query(Event, Organization)
            .outerjoin(Organization, Organization.id == Event.organization_id)
            .filter(Event.id == event_id)
            .first()
        )

    def get_organization(self, organization_id: int) -> Organization | None:
        return self.db.query(Organization).filter(Organization.id == organization_id).first()

    def list_events(self, filters: EventFilterParams) -> tuple[int, list[tuple[Event, Organization | None]]]:
        q = (
            self.db.query(Event, Organization)
            .outerjoin(Organization, Organization.id == Event.organization_id)
            .filter(Event.is_published.is_(True), Event.is_archived.is_(False))
        )
        if filters.q:
            like = f"%{filters.q.lower()}%"
            q = q.filter(
                or_(
                    func.lower(Event.title).like(like),
                    func.lower(Event.summary).like(like),
                    func.lower(Event.description).like(like),
                )
            )
        if filters.city:
            q = q.filter(func.lower(Event.city) == filters.city.lower())
        if filters.format and filters.format != "all":
            q = q.filter(Event.format == filters.format)
        if filters.help_types:
            q = q.filter(Event.help_type.in_(filters.help_types))
        if filters.starts_from is not None:
            q = q.filter(Event.starts_at >= filters.starts_from)
        if filters.starts_to is not None:
            q = q.filter(Event.starts_at <= filters.starts_to)

        rows = q.all()
        if filters.nearby and filters.latitude is not None and filters.longitude is not None:
            kept: list[tuple[Event, Organization | None]] = []
            for event, org in rows:
                if event.latitude is None or event.longitude is None:
                    continue
                dist = _haversine_km(filters.latitude, filters.longitude, event.latitude, event.longitude)
                if dist <= filters.radius_km:
                    kept.append((event, org))
            rows = kept

        if filters.sort_by == "title":
            rows.sort(key=lambda x: (x[0].title.lower(), x[0].id))
        else:
            rows.sort(key=lambda x: (x[0].starts_at, x[0].id))
        total = len(rows)
        return total, rows[filters.offset : filters.offset + filters.limit]
