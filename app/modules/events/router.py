from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.modules.events.repository import EventRepository
from app.modules.events.schemas import (
    EventCatalogsResponse,
    EventCreateRequest,
    EventDetail,
    EventFilterParams,
    EventListResponse,
    EventUpdateRequest,
)
from app.modules.events.service import EventService

router = APIRouter(prefix="/events", tags=["events"])


def get_event_service(db: Session = Depends(get_db)) -> EventService:
    return EventService(EventRepository(db))


@router.get("", response_model=EventListResponse)
def list_events(
    q: str | None = Query(default=None),
    city: str | None = Query(default=None),
    nearby: bool | None = Query(default=None),
    latitude: float | None = Query(default=None),
    longitude: float | None = Query(default=None),
    radius_km: float = Query(default=50.0, ge=1.0, le=500.0),
    format: str | None = Query(default=None, description="online | offline | all"),
    help_types: str | None = Query(default=None, description="Через запятую: adoption,cleanup,..."),
    starts_from: datetime | None = Query(default=None),
    starts_to: datetime | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="starts_at"),
    service: EventService = Depends(get_event_service),
):
    help_list: list[str] = []
    if help_types:
        help_list = [x.strip() for x in help_types.split(",") if x.strip()]
    filters = EventFilterParams(
        q=q,
        city=city,
        nearby=nearby,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        format=format,
        help_types=help_list,
        starts_from=starts_from,
        starts_to=starts_to,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
    )
    return service.list_events(filters)


@router.get("/catalogs", response_model=EventCatalogsResponse)
def event_catalogs(service: EventService = Depends(get_event_service)):
    return service.get_catalogs()


@router.get("/{event_id}", response_model=EventDetail)
def event_detail(event_id: int, service: EventService = Depends(get_event_service)):
    return service.get_detail(event_id)


@router.post("", response_model=EventDetail)
def create_event(
    payload: EventCreateRequest,
    user: User = Depends(require_roles(UserRole.ORGANIZATION)),
    service: EventService = Depends(get_event_service),
):
    return service.create_event(user, payload)


@router.patch("/{event_id}", response_model=EventDetail)
def update_event(
    event_id: int,
    payload: EventUpdateRequest,
    user: User = Depends(require_roles(UserRole.ORGANIZATION)),
    service: EventService = Depends(get_event_service),
):
    return service.update_event(event_id, user, payload)


@router.post("/{event_id}/archive", response_model=EventDetail)
def archive_event(
    event_id: int,
    user: User = Depends(require_roles(UserRole.ORGANIZATION)),
    service: EventService = Depends(get_event_service),
):
    return service.archive_event(event_id, user)


@router.delete("/{event_id}")
def delete_event(
    event_id: int,
    user: User = Depends(require_roles(UserRole.ORGANIZATION)),
    service: EventService = Depends(get_event_service),
):
    service.delete_event(event_id, user)
    return {"ok": True}
