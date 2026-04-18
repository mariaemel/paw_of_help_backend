from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.volunteers.repository import VolunteerRepository
from app.modules.volunteers.schemas import (
    VolunteerCatalogsResponse,
    VolunteerFilterParams,
    VolunteerListResponse,
)
from app.modules.volunteers.service import VolunteerService

router = APIRouter(prefix="/volunteers", tags=["volunteers"])


def get_volunteer_service(db: Session = Depends(get_db)) -> VolunteerService:
    return VolunteerService(VolunteerRepository(db))


@router.get("", response_model=VolunteerListResponse)
def list_volunteers(
    q: str | None = Query(default=None),
    city: str | None = Query(default=None),
    animal_category: str | None = Query(default=None),
    has_transport: bool | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="name"),
    service: VolunteerService = Depends(get_volunteer_service),
):
    filters = VolunteerFilterParams(
        q=q,
        city=city,
        animal_category=animal_category,
        has_transport=has_transport,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
    )
    return service.list_volunteers(filters)


@router.get("/catalogs", response_model=VolunteerCatalogsResponse)
def volunteer_catalogs(service: VolunteerService = Depends(get_volunteer_service)):
    return service.get_catalogs()
