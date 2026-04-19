from app.modules.animals.display_catalog import SPECIES_LABELS


def species_label_ru(species: str | None, sex: str | None) -> str:
    s = (species or "cat").lower()
    x = (sex or "unknown").lower()
    if s == "dog":
        return "Собака"
    if s == "other":
        return "Другое"
    if s == "cat":
        if x == "male":
            return "Кот"
        if x == "female":
            return "Кошка"
        return "Кошка"
    return SPECIES_LABELS.get(s, s)

