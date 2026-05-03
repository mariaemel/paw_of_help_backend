from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

WeekdaySlug = Literal[
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
]


class VolunteerTimeRange(BaseModel):
    start: str = Field(description="HH:MM")
    end: str = Field(description="HH:MM")

    @field_validator("start", "end")
    @classmethod
    def time_hhmm(cls, v: str) -> str:
        s = v.strip()
        if len(s) != 5 or s[2] != ":":
            raise ValueError("Ожидается формат HH:MM")
        h, m = s[:2], s[3:5]
        if not (h.isdigit() and m.isdigit()):
            raise ValueError("Ожидается формат HH:MM")
        if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
            raise ValueError("Некорректное время")
        return f"{int(h):02d}:{int(m):02d}"


class VolunteerWeeklySlot(BaseModel):
    weekday: WeekdaySlug
    ranges: list[VolunteerTimeRange] = Field(default_factory=list)


class VolunteerListItem(BaseModel):
    user_id: int
    full_name: str | None = None
    avatar_url: str | None = None
    location_city: str | None = None
    experience_level: str | None = None
    experience_level_label: str | None = None
    completed_tasks_count: int = 0
    is_available: bool = True
    competency_tags: list[str] = Field(default_factory=list)
    animal_types: list[str] = Field(default_factory=list)
    travel_radius_km: int | None = None
    availability: str | None = None

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
    help_formats: list[CatalogOption]
    travel_area_modes: list[CatalogOption]
    weekdays: list[CatalogOption]


class VolunteerWeekdayScheduleOut(BaseModel):
    weekday: str
    weekday_label: str
    ranges: list[VolunteerTimeRange]


class VolunteerPublicLogistics(BaseModel):
    weekly_schedule: list[VolunteerWeekdayScheduleOut] = Field(default_factory=list)
    accepts_night_urgency: bool = False
    night_urgency_label: str | None = Field(
        default=None, description="Подпись при ночных выездах, если отмечено в ЛК"
    )
    travel_area_mode: str | None = None
    travel_area_label: str | None = None


class VolunteerPublicArticleCard(BaseModel):
    id: int
    title: str
    summary: str | None = None
    read_minutes: int = 5
    category: str
    category_label: str


class VolunteerViewerActions(BaseModel):
    can_write_message: bool = False
    can_offer_task: bool = False


class VolunteerDetail(BaseModel):

    user_id: int
    full_name: str | None = None
    avatar_url: str | None = None
    completed_tasks_count: int = 0

    readiness_status: Literal["available", "paused"] = "available"
    readiness_label: str = "Готов к задачам"

    hero_experience_badges: list[str] = Field(default_factory=list)

    location_city: str | None = None
    location_district: str | None = None
    location_display: str | None = Field(
        default=None, description="Город и район одной строкой"
    )

    help_format: str | None = None
    help_format_label: str | None = None

    competency_slugs: list[str] = Field(default_factory=list)
    competency_tags: list[str] = Field(default_factory=list, description="Подписи чипов для UI")

    animal_category_ids: list[str] = Field(default_factory=list)
    animal_category_labels: list[str] = Field(default_factory=list)

    logistics: VolunteerPublicLogistics | None = None

    about_me: str | None = None

    articles: list[VolunteerPublicArticleCard] = Field(default_factory=list)

    viewer: VolunteerViewerActions = Field(default_factory=VolunteerViewerActions)

    travel_radius_km: int | None = Field(
        default=None, description="Радиус путешествий волонтёра в километрах"
    )
