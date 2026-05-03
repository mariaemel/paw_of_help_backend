from pydantic import BaseModel, Field


class HelpMonetaryBrief(BaseModel):
    request_id: int
    help_bucket: str = Field(description="heal | feed | other")
    line: str
    amount_rub: float | None = None


class HelpAnimalCard(BaseModel):
    animal_id: int
    name: str
    species_tag: str
    age_tag: str
    status_chip: str | None = None
    organization_name: str | None = None
    location_city: str | None = None
    is_urgent: bool = False

    monetary: list[HelpMonetaryBrief] = Field(
        default_factory=list,
        description="Все связанные заявки раздела (по типу заявки). Клиент фильтрует по активной вкладке.",
    )
    adopt_ready: bool = Field(description="Животное может участвовать во вкладке «Приютить»")
    primary_photo_url: str | None = None


class HelpListResponse(BaseModel):
    tab: str
    total: int
    items: list[HelpAnimalCard]
