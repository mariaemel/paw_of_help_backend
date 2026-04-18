from app.modules.animals.constants import SPECIES_LABELS


def age_label_months(age_months: int) -> str:
    if age_months < 12:
        return f"{age_months} мес."
    years = age_months // 12
    if years == 1:
        return "1 год"
    if 2 <= years <= 4:
        return f"{years} года"
    return f"{years} лет"


def build_card_tags(species: str, breed: str | None, age_months: int) -> list[str]:
    kind = SPECIES_LABELS.get(species, species)
    breed_tag = breed.strip() if breed and breed.strip() else "Метис"
    return [kind, breed_tag, age_label_months(age_months)]
