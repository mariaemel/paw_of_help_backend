import json

from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.schemas import (
    OrganizationCatalogsResponse,
    OrganizationFilterParams,
    OrganizationListItem,
    OrganizationListResponse,
)


class OrganizationService:
    def __init__(self, repo: OrganizationRepository):
        self.repo = repo

    def list_orgs(self, filters: OrganizationFilterParams) -> OrganizationListResponse:
        total, items = self.repo.list_organizations(filters)
        out: list[OrganizationListItem] = []
        for org in items:
            raw = org.needs_json or "[]"
            try:
                needs = json.loads(raw)
                if not isinstance(needs, list):
                    needs = []
            except json.JSONDecodeError:
                needs = []
            out.append(
                OrganizationListItem(
                    id=org.id,
                    name=org.name,
                    city=org.city,
                    address=org.address,
                    specialization=org.specialization,
                    wards_count=org.wards_count,
                    adopted_yearly_count=org.adopted_yearly_count,
                    needs=[str(x) for x in needs],
                    description=org.description,
                )
            )
        return OrganizationListResponse(total=total, items=out)

    def get_catalogs(self) -> OrganizationCatalogsResponse:
        cities, specs, needs_opts = self.repo.list_organization_catalogs()
        return OrganizationCatalogsResponse(
            cities=cities,
            specializations=specs,
            needs_options=needs_opts,
        )
