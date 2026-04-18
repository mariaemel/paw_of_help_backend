from pydantic import BaseModel, ConfigDict, Field


class OrganizationListItem(BaseModel):
    id: int
    name: str
    city: str | None = None
    address: str | None = None
    specialization: str
    wards_count: int
    adopted_yearly_count: int
    needs: list[str] = Field(default_factory=list)
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationListResponse(BaseModel):
    total: int
    items: list[OrganizationListItem]


class OrganizationFilterParams(BaseModel):
    q: str | None = None
    city: str | None = None
    specialization: str | None = None
    needs: list[str] = Field(default_factory=list)
    nearby: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float | None = Field(default=50.0, ge=1.0, le=500.0)
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="name")


class OrganizationCatalogsResponse(BaseModel):
    cities: list[str]
    specializations: list[str]
    needs_options: list[dict[str, str]]

