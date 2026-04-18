from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.schemas import (
    OrganizationCatalogsResponse,
    OrganizationFilterParams,
    OrganizationListResponse,
)
from app.modules.organizations.service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


def get_org_service(db: Session = Depends(get_db)) -> OrganizationService:
    return OrganizationService(OrganizationRepository(db))


@router.get("", response_model=OrganizationListResponse)
def list_organizations(
    q: str | None = Query(default=None),
    city: str | None = Query(default=None),
    specialization: str | None = Query(default=None, description="cat | dog | all"),
    needs: str | None = Query(default=None, description="Через запятую: urgent,volunteers,..."),
    nearby: bool | None = Query(default=None),
    latitude: float | None = Query(default=None),
    longitude: float | None = Query(default=None),
    radius_km: float | None = Query(default=50.0, ge=1.0, le=500.0),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="name"),
    service: OrganizationService = Depends(get_org_service),
):
    need_list: list[str] = []
    if needs:
        need_list = [x.strip() for x in needs.split(",") if x.strip()]
    filters = OrganizationFilterParams(
        q=q,
        city=city,
        specialization=specialization,
        needs=need_list,
        nearby=nearby,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
    )
    return service.list_orgs(filters)


@router.get("/catalogs", response_model=OrganizationCatalogsResponse)
def org_catalogs(service: OrganizationService = Depends(get_org_service)):
    return service.get_catalogs()
