from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.animals.repository import AnimalRepository
from app.modules.animals.schemas import (
    AnimalCatalogsResponse,
    AnimalDetail,
    AnimalFilterParams,
    AnimalListResponse,
    AnimalPhotoUploadResponse,
)
from app.modules.animals.service import AnimalService

router = APIRouter(prefix="/animals", tags=["animals"])


def get_animal_service(db: Session = Depends(get_db)) -> AnimalService:
    return AnimalService(AnimalRepository(db))


@router.get("", response_model=AnimalListResponse)
def list_animals(
    q: str | None = Query(default=None),
    city: str | None = Query(default=None),
    status: str | None = Query(default=None),
    sex: str | None = Query(default=None),
    is_urgent: bool | None = Query(default=None),
    min_age_months: int | None = Query(default=None, ge=0),
    max_age_months: int | None = Query(default=None, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at"),
    service: AnimalService = Depends(get_animal_service),
):
    filters = AnimalFilterParams(
        q=q,
        city=city,
        status=status,
        sex=sex,
        is_urgent=is_urgent,
        min_age_months=min_age_months,
        max_age_months=max_age_months,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
    )
    return service.get_catalog(filters)


@router.get("/catalogs", response_model=AnimalCatalogsResponse)
def get_catalogs(service: AnimalService = Depends(get_animal_service)):
    return service.get_filters_catalogs()


@router.get("/{animal_id}", response_model=AnimalDetail)
def get_animal_card(animal_id: int, service: AnimalService = Depends(get_animal_service)):
    return service.get_card(animal_id)


@router.post("/{animal_id}/images", response_model=AnimalPhotoUploadResponse)
def upload_animal_image(
    animal_id: int,
    file: UploadFile = File(...),
    is_primary: bool = Query(default=False),
    service: AnimalService = Depends(get_animal_service),
):
    return service.upload_image(animal_id=animal_id, file=file, is_primary=is_primary)
