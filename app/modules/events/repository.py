from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.core.geo import filter_sort_paginate_nearby
from app.core.list_query import apply_city_filter, apply_text_search, geo_bbox_clauses
from app.models.event import Event
from app.models.organization import Organization
from app.modules.events.schemas import EventFilterParams


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

    def _list_events_query(self, filters: EventFilterParams):
        q = (
            self.db.query(Event, Organization)
            .outerjoin(Organization, Organization.id == Event.organization_id)
            .filter(Event.is_published.is_(True), Event.is_archived.is_(False))
        )
        q = apply_text_search(q, filters.q, Event.title, Event.summary)
        q = apply_city_filter(q, Event.city, filters.city)
        if filters.format and filters.format != "all":
            q = q.filter(Event.format == filters.format)
        if filters.help_types:
            q = q.filter(Event.help_type.in_(filters.help_types))
        if filters.starts_from is not None:
            q = q.filter(Event.starts_at >= filters.starts_from)
        if filters.starts_to is not None:
            q = q.filter(Event.starts_at <= filters.starts_to)
        return q

    def list_events(self, filters: EventFilterParams) -> tuple[int, list[tuple[Event, Organization | None]]]:
        q = self._list_events_query(filters)

        if filters.nearby and filters.latitude is not None and filters.longitude is not None:
            radius = filters.radius_km or 50.0
            q = q.filter(
                *geo_bbox_clauses(Event.latitude, Event.longitude, filters.latitude, filters.longitude, radius)
            )
            candidates: list[tuple[Event, Organization | None]] = q.all()
            if filters.sort_by == "title":
                sort_fn = lambda row: (row[0].title.lower(), row[0].id)
            else:
                sort_fn = lambda row: (row[0].starts_at, row[0].id)

            return filter_sort_paginate_nearby(
                candidates,
                center_lat=filters.latitude,
                center_lon=filters.longitude,
                radius_km=radius,
                get_lat_lon=lambda row: (row[0].latitude, row[0].longitude),
                sort_key=sort_fn,
                offset=filters.offset,
                limit=filters.limit,
            )

        total = q.order_by(None).count()
        if filters.sort_by == "title":
            q = q.order_by(asc(Event.title), asc(Event.id))
        else:
            q = q.order_by(asc(Event.starts_at), asc(Event.id))

        rows = q.offset(filters.offset).limit(filters.limit).all()
        return total, rows
