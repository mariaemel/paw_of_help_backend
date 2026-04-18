from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.volunteers.repository import VolunteerRepository
from app.modules.volunteers.schemas import (
    VolunteerCatalogsResponse,
    VolunteerDetail,
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
    animal_category: str | None = Query(
        default=None, description="cat | dog | all — с кем готов работать волонтёр"
    ),
    competencies: str | None = Query(
        default=None, description="Через запятую: walk,photo_video,auto,..."
    ),
    experience_levels: str | None = Query(
        default=None, description="Через запятую: beginner,experienced,vet_education"
    ),
    has_transport: bool | None = Query(default=None),
    nearby: bool | None = Query(default=None, description="Волонтёры в радиусе от точки"),
    latitude: float | None = Query(default=None),
    longitude: float | None = Query(default=None),
    radius_km: float | None = Query(default=50.0, ge=1.0, le=500.0),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(
        default="name",
        description="name | city | rating | available_first (сначала свободные)",
    ),
    service: VolunteerService = Depends(get_volunteer_service),
):
    comp_list: list[str] = []
    if competencies:
        comp_list = [x.strip() for x in competencies.split(",") if x.strip()]
    exp_list: list[str] = []
    if experience_levels:
        exp_list = [x.strip() for x in experience_levels.split(",") if x.strip()]

    filters = VolunteerFilterParams(
        q=q,
        city=city,
        animal_category=animal_category,
        competencies=comp_list,
        experience_levels=exp_list,
        has_transport=has_transport,
        nearby=nearby,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km or 50.0,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
    )
    return service.list_volunteers(filters)


@router.get("/catalogs", response_model=VolunteerCatalogsResponse)
def volunteer_catalogs(service: VolunteerService = Depends(get_volunteer_service)):
    return service.get_catalogs()


@router.get("/{volunteer_id}", response_model=VolunteerDetail)
def get_volunteer(volunteer_id: int, service: VolunteerService = Depends(get_volunteer_service)):
    return service.get_volunteer_detail(volunteer_id)
