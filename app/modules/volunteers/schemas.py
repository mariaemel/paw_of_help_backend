from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VolunteerListItem(BaseModel):
    user_id: int
    full_name: str | None = None
    avatar_url: str | None = None
    rating: float = 0.0
    location_city: str | None = None
    experience_level: str | None = None
    experience_level_label: str | None = None
    completed_tasks_count: int = 0
    is_available: bool = True
    competency_tags: list[str] = Field(default_factory=list)
    animal_types: list[str] = Field(default_factory=list)
    travel_radius_km: int | None = None
    availability: str | None = None
    skills: str | None = None
    experience: str | None = None
    preferred_help_format: str | None = None
    animal_categories: str | None = None

    model_config = ConfigDict(from_attributes=True)


class VolunteerListResponse(BaseModel):
    total: int
    items: list[VolunteerListItem]


class VolunteerFilterParams(BaseModel):
    q: str | None = None
    city: str | None = None
    animal_category: str | None = Field(
        default=None, description="cat | dog | all — с кем готов работать волонтёр"
    )
    competencies: list[str] = Field(default_factory=list)
    experience_levels: list[str] = Field(default_factory=list)
    has_transport: bool | None = None
    nearby: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float = Field(default=50.0, ge=1.0, le=500.0)
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="name")


class CatalogOption(BaseModel):
    id: str
    label: str


class VolunteerCatalogsResponse(BaseModel):
    cities: list[str]
    competencies: list[CatalogOption]
    experience_levels: list[CatalogOption]
    animal_types: list[CatalogOption]


class VolunteerReviewItem(BaseModel):
    author_name: str
    author_avatar_url: str | None = None
    review_date: datetime
    rating: int = Field(ge=1, le=5)
    text: str

    model_config = ConfigDict(from_attributes=True)


class VolunteerDetail(BaseModel):
    user_id: int
    full_name: str | None = None
    avatar_url: str | None = None
    rating: float = 0.0
    location_city: str | None = None
    travel_radius_km: int | None = None
    competencies: list[str] = Field(default_factory=list)
    competency_labels: list[str] = Field(default_factory=list)
    about_me: str | None = None
    animal_types: list[str] = Field(default_factory=list)
    animal_type_labels: list[str] = Field(default_factory=list)
    availability: str | None = None
    completed_tasks_count: int = 0
    experience_level: str | None = None
    experience_level_label: str | None = None
    is_available: bool = True
    reviews: list[VolunteerReviewItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
