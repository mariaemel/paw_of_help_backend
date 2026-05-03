from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


KB_CATEGORY_OPTIONS: list[dict[str, str]] = [
    {"id": "care", "label": "Уход"},
    {"id": "first_aid", "label": "Первая помощь"},
    {"id": "adaptation", "label": "Адаптация"},
    {"id": "socialization", "label": "Социализация"},
    {"id": "training", "label": "Воспитание"},
    {"id": "treatment", "label": "Лечение"},
    {"id": "legal", "label": "Юридические вопросы"},
]


class CatalogOption(BaseModel):
    id: str
    label: str


class KnowledgeListItem(BaseModel):
    id: int
    title: str
    summary: str | None = None
    category: str
    category_label: str | None = None
    read_minutes: int
    is_context_tip: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDetail(BaseModel):
    id: int
    title: str
    summary: str | None = None
    content: str
    category: str
    category_label: str | None = None
    read_minutes: int
    is_context_tip: bool
    owner_role: str
    created_at: datetime
    updated_at: datetime


class KnowledgeListResponse(BaseModel):
    total: int
    items: list[KnowledgeListItem]


class KnowledgeCatalogsResponse(BaseModel):
    categories: list[CatalogOption]
    tip_scope_options: list[CatalogOption]


class KnowledgeFilterParams(BaseModel):
    q: str | None = None
    category: str | None = None
    only_context_tips: bool | None = None
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="-created_at")


class KnowledgeUpsertRequest(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    summary: str | None = Field(default=None, max_length=500)
    content: str = Field(min_length=10)
    category: str
    is_context_tip: bool = False
    is_published: bool = True


class KnowledgeUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    summary: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, min_length=10)
    category: str | None = None
    is_context_tip: bool | None = None
    is_published: bool | None = None
