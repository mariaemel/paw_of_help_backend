from pydantic import BaseModel, ConfigDict, Field


class VolunteerListItem(BaseModel):
    user_id: int
    full_name: str | None = None
    location_city: str | None = None
    skills: str | None = None
    experience: str | None = None
    availability: str | None = None
    travel_radius_km: int | None = None
    preferred_help_format: str | None = None
    animal_categories: str | None = None

    model_config = ConfigDict(from_attributes=True)


class VolunteerListResponse(BaseModel):
    total: int
    items: list[VolunteerListItem]


class VolunteerFilterParams(BaseModel):
    q: str | None = None
    city: str | None = None
    animal_category: str | None = None
    has_transport: bool | None = None
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="name")


class VolunteerCatalogsResponse(BaseModel):
    cities: list[str]
