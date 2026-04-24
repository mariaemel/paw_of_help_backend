from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.urgent.repository import UrgentRepository
from app.modules.urgent.schemas import (
    UrgentCatalogsResponse,
    UrgentFilterParams,
    UrgentListResponse,
    UrgentRequestCreate,
    UrgentRequestDetail,
    UrgentRequestUpdate,
)
from app.modules.urgent.service import UrgentService

router = APIRouter(prefix="/urgent", tags=["urgent"])


def get_urgent_service(db: Session = Depends(get_db)) -> UrgentService:
    return UrgentService(UrgentRepository(db))


@router.get("", response_model=UrgentListResponse)
def list_urgent(
    q: str | None = Query(default=None),
    city: str | None = Query(default=None),
    animal_species: str | None = Query(default=None, description="cat | dog | all"),
    help_types: str | None = Query(default=None, description="Через запятую: financial,auto,..."),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="-created_at"),
    service: UrgentService = Depends(get_urgent_service),
):
    help_list: list[str] = []
    if help_types:
        help_list = [x.strip() for x in help_types.split(",") if x.strip()]
    filters = UrgentFilterParams(
        q=q,
        city=city,
        animal_species=animal_species,
        help_types=help_list,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
    )
    return service.list_urgent(filters)


@router.get("/catalogs", response_model=UrgentCatalogsResponse)
def urgent_catalogs(service: UrgentService = Depends(get_urgent_service)):
    return service.get_catalogs()


@router.get("/{request_id}", response_model=UrgentRequestDetail)
def urgent_detail(request_id: int, service: UrgentService = Depends(get_urgent_service)):
    return service.get_detail(request_id)


@router.post("", response_model=UrgentRequestDetail)
def create_urgent(payload: UrgentRequestCreate, service: UrgentService = Depends(get_urgent_service)):
    return service.create_request(payload)


@router.patch("/{request_id}", response_model=UrgentRequestDetail)
def update_urgent(
    request_id: int,
    payload: UrgentRequestUpdate,
    service: UrgentService = Depends(get_urgent_service),
):
    return service.update_request(request_id, payload)


@router.post("/{request_id}/close", response_model=UrgentRequestDetail)
def close_urgent(
    request_id: int,
    actor_user_id: int = Query(...),
    actor_role: str = Query(..., description="organization"),
    service: UrgentService = Depends(get_urgent_service),
):
    return service.close_request(request_id, actor_user_id, actor_role)
