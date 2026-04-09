from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnimalListItem(BaseModel):
    id: int
    name: str
    sex: str
    age_months: int
    location_city: str | None = None
    is_urgent: bool
    status: str
    short_story: str | None = None
    primary_photo_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AnimalDetail(AnimalListItem):
    health_info: str | None = None
    character_info: str | None = None
    help_options: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime
    photo_urls: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AnimalListResponse(BaseModel):
    total: int
    items: list[AnimalListItem]


class AnimalCatalogsResponse(BaseModel):
    statuses: list[str]
    sexes: list[str]
    cities: list[str]
    urgent_options: list[bool]


class AnimalFilterParams(BaseModel):
    q: str | None = None
    city: str | None = None
    status: str | None = None
    sex: str | None = None
    is_urgent: bool | None = None
    min_age_months: int | None = Field(default=None, ge=0)
    max_age_months: int | None = Field(default=None, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="created_at")


class AnimalPhotoUploadResponse(BaseModel):
    id: int
    animal_id: int
    is_primary: bool
    url: str
