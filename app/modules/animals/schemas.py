from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class OrganizationBrief(BaseModel):
    id: int
    name: str
    city: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AnimalListItem(BaseModel):
    id: int
    name: str
    species: str
    sex: str
    age_months: int
    location_city: str | None = None
    is_urgent: bool
    status: str
    short_story: str | None = None
    primary_photo_url: str | None = None
    breed: str | None = None
    card_tags: list[str] = Field(default_factory=list)
    organization_id: int | None = None
    organization_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AnimalDetail(BaseModel):
    id: int
    name: str
    species: str
    breed: str | None = None
    sex: str
    age_months: int
    location_city: str | None = None
    is_urgent: bool
    status: str
    short_story: str | None = None
    full_description: str | None = None
    primary_photo_url: str | None = None
    photo_urls: list[str] = Field(default_factory=list)
    card_tags: list[str] = Field(default_factory=list)
    organization: OrganizationBrief | None = None
    health_checklist: list[str] = Field(default_factory=list)
    health_features: str | None = None
    treatment_required: str | None = None
    health_info: str | None = None
    character_tags: list[str] = Field(default_factory=list)
    character_info: str | None = None
    help_options: str | None = None
    urgent_needs_text: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnimalListResponse(BaseModel):
    total: int
    items: list[AnimalListItem]


class AgeGroupOption(BaseModel):
    id: str
    label: str
    min_months: int | None = None
    max_months: int | None = None


class FeatureFilterOption(BaseModel):
    id: str
    label: str


class OrganizationOption(BaseModel):
    id: int
    name: str


class AnimalCatalogsResponse(BaseModel):
    statuses: list[str]
    sexes: list[str]
    cities: list[str]
    urgent_options: list[bool]
    species: list[str]
    age_groups: list[AgeGroupOption]
    features: list[FeatureFilterOption]
    organizations: list[OrganizationOption]


class AnimalFilterParams(BaseModel):
    q: str | None = None
    city: str | None = None
    status: str | None = None
    sex: str | None = None
    species: str | None = None
    organization_id: int | None = None
    age_group: str | None = None
    features: list[str] = Field(default_factory=list)
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
