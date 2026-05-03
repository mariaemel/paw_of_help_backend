from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


EVENT_HELP_OPTIONS: list[dict[str, str]] = [
    {"id": "adoption", "label": "Выставки и пристрой"},
    {"id": "cleanup", "label": "Субботники"},
    {"id": "fair", "label": "Ярмарки"},
    {"id": "education", "label": "Обучение и лекции"},
]


class CatalogOption(BaseModel):
    id: str
    label: str


class EventListItem(BaseModel):
    id: int
    title: str
    summary: str | None = None
    organization_name: str | None = None
    city: str | None = None
    address: str | None = None
    format: str
    help_type: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class EventDetail(BaseModel):
    id: int
    title: str
    summary: str | None = None
    description: str
    organization_name: str | None = None
    city: str | None = None
    address: str | None = None
    format: str
    help_type: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None


class EventListResponse(BaseModel):
    total: int
    items: list[EventListItem]


class EventCatalogsResponse(BaseModel):
    cities: list[str]
    formats: list[CatalogOption]
    help_types: list[CatalogOption]


class EventFilterParams(BaseModel):
    q: str | None = None
    city: str | None = None
    nearby: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float = Field(default=50.0, ge=1.0, le=500.0)
    format: str | None = None
    help_types: list[str] = Field(default_factory=list)
    starts_from: datetime | None = None
    starts_to: datetime | None = None
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="starts_at")


class EventCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    summary: str | None = Field(default=None, max_length=500)
    description: str = Field(min_length=10)
    city: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=500)
    format: str = Field(default="offline", description="online | offline")
    help_type: str | None = Field(default=None, description="adoption | cleanup | fair | education")
    starts_at: datetime
    ends_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_published: bool = True


class EventUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    summary: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, min_length=10)
    city: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=500)
    format: str | None = Field(default=None, description="online | offline")
    help_type: str | None = Field(default=None, description="adoption | cleanup | fair | education")
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_published: bool | None = None
