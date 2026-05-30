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
    EventRegistrationResponse,
    EventUpdateRequest,
)


def _event_registration_meta(event: Event) -> dict:
    entry = (event.entry_type or "free").strip().lower()
    capacity = event.capacity
    taken = int(event.seats_taken or 0)
    if entry != "limited" or capacity is None:
        return {
            "entry_type": entry or "free",
            "capacity": capacity,
            "seats_taken": taken,
            "seats_available": None,
            "is_full": False,
            "registration_action": "details",
        }
    available = max(int(capacity) - taken, 0)
    is_full = available <= 0
    return {
        "entry_type": "limited",
        "capacity": int(capacity),
        "seats_taken": taken,
        "seats_available": available,
        "is_full": is_full,
        "registration_action": "full" if is_full else "signup",
    }


class EventService:
    def __init__(self, repo: EventRepository):
        self.repo = repo

    def list_events(self, filters: EventFilterParams) -> EventListResponse:
        total, rows = self.repo.list_events(filters)
        items: list[EventListItem] = []
        for e, org in rows:
            meta = _event_registration_meta(e)
            items.append(
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
                    **meta,
                )
            )
        return EventListResponse(total=total, items=items)

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
        meta = _event_registration_meta(event)
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
            **meta,
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
        meta = _event_registration_meta(event)
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
            **meta,
        )

    def create_event(self, user: User, payload: EventCreateRequest) -> EventDetail:
        org = self._organization_for_user(user)

        entry_type = (payload.entry_type or "free").strip().lower()
        if entry_type not in ("free", "limited"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="entry_type: free | limited")
        if entry_type == "limited" and payload.capacity is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите capacity для limited")

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
            entry_type=entry_type,
            capacity=payload.capacity if entry_type == "limited" else None,
            seats_taken=0,
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
        if payload.entry_type is not None:
            entry = payload.entry_type.strip().lower()
            if entry not in ("free", "limited"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="entry_type: free | limited")
            event.entry_type = entry
            if entry == "free":
                event.capacity = None
            elif event.capacity is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Укажите capacity для limited")
        self.repo.db.commit()
        self.repo.db.refresh(event)
        return self._to_detail(event, owner_org)

    def register_for_event(self, event_id: int) -> EventRegistrationResponse:
        row = self.repo.get_event(event_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        event, _org = row
        meta = _event_registration_meta(event)
        if meta["registration_action"] == "details":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="На это мероприятие не нужна запись")
        if meta["is_full"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Мест больше нет")
        event.seats_taken = int(event.seats_taken or 0) + 1
        self.repo.db.commit()
        self.repo.db.refresh(event)
        meta = _event_registration_meta(event)
        return EventRegistrationResponse(event_id=event.id, **meta)

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
