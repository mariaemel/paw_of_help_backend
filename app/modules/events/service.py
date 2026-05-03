from fastapi import HTTPException, status

from app.models.event import Event
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.modules.events.repository import EventRepository
from app.modules.events.schemas import (
    EVENT_HELP_OPTIONS,
    CatalogOption,
    EventCatalogsResponse,
    EventCreateRequest,
    EventDetail,
    EventFilterParams,
    EventListItem,
    EventListResponse,
    EventUpdateRequest,
)


class EventService:
    def __init__(self, repo: EventRepository):
        self.repo = repo

    def list_events(self, filters: EventFilterParams) -> EventListResponse:
        total, rows = self.repo.list_events(filters)
        return EventListResponse(
            total=total,
            items=[
                EventListItem(
                    id=e.id,
                    title=e.title,
                    summary=e.summary,
                    organization_name=org.name if org else None,
                    city=e.city,
                    address=e.address,
                    format=e.format,
                    help_type=e.help_type,
                    starts_at=e.starts_at,
                    ends_at=e.ends_at,
                )
                for e, org in rows
            ],
        )

    def get_catalogs(self) -> EventCatalogsResponse:
        return EventCatalogsResponse(
            cities=self.repo.list_catalogs(),
            formats=[
                CatalogOption(id="online", label="Онлайн"),
                CatalogOption(id="offline", label="Офлайн"),
                CatalogOption(id="all", label="Все"),
            ],
            help_types=[CatalogOption(**x) for x in EVENT_HELP_OPTIONS],
        )

    def get_detail(self, event_id: int) -> EventDetail:
        row = self.repo.get_event(event_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        event, org = row
        return EventDetail(
            id=event.id,
            title=event.title,
            summary=event.summary,
            description=event.description,
            organization_name=org.name if org else None,
            city=event.city,
            address=event.address,
            format=event.format,
            help_type=event.help_type,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            latitude=event.latitude,
            longitude=event.longitude,
        )

    def _organization_for_user(self, user: User) -> Organization:
        if user.role != UserRole.ORGANIZATION:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization role required")
        org = (
            self.repo.db.query(Organization)
            .filter(Organization.owner_user_id == user.id)
            .order_by(Organization.id.asc())
            .first()
        )
        if org is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization profile not found")
        return org

    @staticmethod
    def _to_detail(event: Event, org: Organization | None) -> EventDetail:
        return EventDetail(
            id=event.id,
            title=event.title,
            summary=event.summary,
            description=event.description,
            organization_name=org.name if org else None,
            city=event.city,
            address=event.address,
            format=event.format,
            help_type=event.help_type,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            latitude=event.latitude,
            longitude=event.longitude,
        )

    def create_event(self, user: User, payload: EventCreateRequest) -> EventDetail:
        org = self._organization_for_user(user)

        event = Event(
            organization_id=org.id,
            title=payload.title,
            summary=payload.summary,
            description=payload.description,
            city=payload.city,
            address=payload.address,
            format=payload.format,
            help_type=payload.help_type,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            latitude=payload.latitude,
            longitude=payload.longitude,
            is_published=payload.is_published,
            is_archived=False,
        )
        self.repo.db.add(event)
        self.repo.db.commit()
        self.repo.db.refresh(event)
        return self._to_detail(event, org)

    def update_event(self, event_id: int, user: User, payload: EventUpdateRequest) -> EventDetail:
        org = self._organization_for_user(user)
        row = self.repo.get_event_for_owner(event_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        event, owner_org = row
        if owner_org is None or owner_org.id != org.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only manage own events")

        for field in (
            "title",
            "summary",
            "description",
            "city",
            "address",
            "format",
            "help_type",
            "starts_at",
            "ends_at",
            "latitude",
            "longitude",
            "is_published",
        ):
            value = getattr(payload, field)
            if value is not None:
                setattr(event, field, value)
        self.repo.db.commit()
        self.repo.db.refresh(event)
        return self._to_detail(event, owner_org)

    def archive_event(self, event_id: int, user: User) -> EventDetail:
        org = self._organization_for_user(user)
        row = self.repo.get_event_for_owner(event_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        event, owner_org = row
        if owner_org is None or owner_org.id != org.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only manage own events")
        event.is_archived = True
        self.repo.db.commit()
        self.repo.db.refresh(event)
        return self._to_detail(event, owner_org)

    def delete_event(self, event_id: int, user: User) -> None:
        org = self._organization_for_user(user)
        row = self.repo.get_event_for_owner(event_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        event, owner_org = row
        if owner_org is None or owner_org.id != org.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only manage own events")
        self.repo.db.delete(event)
        self.repo.db.commit()
