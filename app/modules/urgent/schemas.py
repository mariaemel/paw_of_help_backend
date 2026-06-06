from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.volunteers.constants import COMPETENCY_OPTIONS

HELP_TYPE_OPTIONS: list[dict[str, str]] = [
    {"id": "financial", "label": "Финансовая помощь"},
    {"id": "foster", "label": "Передержка"},
    {"id": "manual", "label": "Помощь руками"},
    {"id": "auto", "label": "Автопомощь"},
    {"id": "medical", "label": "Лекарства и кровь"},
    {"id": "food", "label": "Корм"},
]

VOLUNTEER_TASK_TYPE_OPTIONS: list[dict[str, str]] = COMPETENCY_OPTIONS

FUNDRAISING_HELP_TYPE_IDS = frozenset({"financial", "food", "medical", "feed"})


class CatalogOption(BaseModel):
    id: str
    label: str


class HelpRequestPaymentDetails(BaseModel):
    bank_account: str | None = None


class UrgentRequestListItem(BaseModel):
    id: int
    title: str
    description: str
    city: str | None = None
    organization_id: int
    organization_name: str
    animal_id: int | None = None
    animal_name: str | None = None
    animal_species: str | None = None
    help_type: str
    is_urgent: bool
    volunteer_needed: bool
    deadline_at: datetime | None = None
    deadline_note: str | None = None
    deadline_label: str | None = None
    status: str
    target_amount: float | None = None
    primary_photo_url: str | None = None
    animal_photo_url: str | None = Field(
        default=None,
        description="Фото связанного животного (дублирует primary_photo_url, если заявка привязана к питомцу)",
    )
    payment_details: HelpRequestPaymentDetails = Field(
        default_factory=HelpRequestPaymentDetails,
        description="Счёт для перевода: заявки или организации",
    )
    uses_organization_payment_details: bool = True
    is_published: bool = True
    badges: list[str] = Field(default_factory=list)


class UrgentRequestDetail(UrgentRequestListItem):
    bank_account_override: str | None = Field(
        default=None,
        description="Счёт заявки, если отличается от счёта организации (для формы редактирования)",
    )
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    volunteer_requirements: str | None = None
    volunteer_competencies: list[str] = Field(default_factory=list)
    media_url: str | None = None
    created_at: datetime
    updated_at: datetime


class UrgentListResponse(BaseModel):
    total: int
    items: list[UrgentRequestListItem]


class UrgentCatalogsResponse(BaseModel):
    cities: list[str]
    species: list[CatalogOption]
    help_types: list[CatalogOption]
    volunteer_task_types: list[CatalogOption] = Field(
        default_factory=list,
        description="Типы помощи для заявок «нужен волонтёр» (slug компетенций)",
    )
    statuses: list[CatalogOption]


class UrgentFilterParams(BaseModel):
    q: str | None = None
    city: str | None = None
    animal_species: str | None = None
    help_types: list[str] = Field(default_factory=list)
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="-created_at")


class UrgentRequestCreate(BaseModel):
    animal_id: int | None = None
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10)
    city: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=500)
    latitude: float | None = None
    longitude: float | None = None
    help_type: str
    is_urgent: bool = True
    volunteer_needed: bool = False
    volunteer_requirements: str | None = None
    volunteer_competencies: list[str] = Field(default_factory=list)
    target_amount: float | None = None
    deadline_at: datetime | None = None
    deadline_note: str | None = Field(default=None, max_length=255)
    media_path: str | None = None
    bank_account: str | None = Field(
        default=None,
        max_length=64,
        description="Счёт для этой заявки; сохраняется только если отличается от счёта организации",
    )
    status: str = Field(default="open", description="open | in_progress | closed")
    is_published: bool = Field(
        default=False,
        description="False — черновик; не попадает в публичные ленты до публикации",
    )


class UrgentRequestUpdate(BaseModel):
    animal_id: int | None = None
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=10)
    city: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=500)
    latitude: float | None = None
    longitude: float | None = None
    help_type: str | None = None
    is_urgent: bool | None = None
    volunteer_needed: bool | None = None
    volunteer_requirements: str | None = None
    volunteer_competencies: list[str] | None = None
    target_amount: float | None = None
    deadline_at: datetime | None = None
    deadline_note: str | None = Field(default=None, max_length=255)
    media_path: str | None = None
    bank_account: str | None = Field(default=None, max_length=64)
    status: str | None = Field(default=None, description="open | in_progress | closed")
    is_published: bool | None = None


