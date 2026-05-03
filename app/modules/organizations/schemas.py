from datetime import date, datetime

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
    logo_url: str | None = None

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


class SocialLinkItem(BaseModel):
    label: str = Field(description="Например: Telegram, ВКонтакте")
    url: str


class OrgPublicHero(BaseModel):
    name: str
    tagline: str | None = None
    description: str | None = None
    city: str | None = None
    region: str | None = None
    geography_display: str | None = Field(
        default=None,
        description="Готовая строка для UI: город и регион",
    )
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    social_links: list[SocialLinkItem] = Field(default_factory=list)
    logo_url: str | None = None
    cover_url: str | None = None
    wards_count: int = 0
    adopted_yearly_count: int = 0
    has_chat_contact: bool = False
    admission_rules: str | None = Field(default=None, description="Текст правил приёма")
    adoption_howto: str | None = Field(default=None, description="Текст как приютить питомца")


class OrgPublicHelpSection(BaseModel):
    kind: str
    title: str
    description: str
    primary_action: str = Field(description="help | respond | contact — сценарий для кнопки на клиенте")


class OrgPublicUrgentNeed(BaseModel):
    id: int
    title: str
    description: str
    help_type: str
    is_urgent: bool
    animal_id: int | None = None
    volunteer_needed: bool = False


class OrgPublicWardCard(BaseModel):
    id: int
    name: str
    species: str
    age_months: int
    status: str
    status_label: str
    photo_url: str | None = None
    is_urgent: bool = False
    open_help_request_id: int | None = None


class OrgPublicAbout(BaseModel):
    is_empty: bool = False
    founded_year: int | None = None
    about: str | None = Field(default=None, description="Описание и история организации (простой текст)")
    gallery_urls: list[str] = Field(default_factory=list)
    inn: str | None = None
    ogrn: str | None = None
    bank_account: str | None = None


class OrgPublicEvent(BaseModel):
    id: int
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    description: str
    location_display: str | None = None


class OrgPublicReport(BaseModel):
    id: int
    title: str
    published_at: datetime
    summary: str | None = None


class OrgPublicArticle(BaseModel):
    id: int
    title: str
    category: str
    read_minutes: int


class OrgPublicHomeStory(BaseModel):
    id: int
    animal_name: str
    story: str
    photo_url: str | None = None
    adopted_at: date


class OrganizationPublicPage(BaseModel):
    hero: OrgPublicHero
    wards: list[OrgPublicWardCard]
    about: OrgPublicAbout
    help_sections: list[OrgPublicHelpSection]
    urgent_help: list[OrgPublicUrgentNeed]
    events: list[OrgPublicEvent]
    reports: list[OrgPublicReport]
    articles: list[OrgPublicArticle]
    home_stories: list[OrgPublicHomeStory]

