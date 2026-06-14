from __future__ import annotations

# (male, female) — для нейтральных фраз обе формы одинаковые
_CATALOG_LABELS_BY_KIND: dict[str, dict[str, tuple[str, str]]] = {
    "health_care": {
        "vaccinated": ("Привит", "Привита"),
        "sterilized": ("Кастрирован", "Стерилизована"),
        "vaccinated_full": ("Комплексно привит", "Комплексно привита"),
        "dewormed": ("Обработан от паразитов", "Обработана от паразитов"),
    },
    "character": {
        "calm": ("Спокойный", "Спокойная"),
        "affectionate": ("Ласковый", "Ласковая"),
        "afraid_loud": ("Боится громких звуков", "Боится громких звуков"),
        "friendly": ("Дружелюбный", "Дружелюбная"),
        "active": ("Активный", "Активная"),
        "contact": ("Контактный", "Контактная"),
        "litter_trained": ("Приучен к лотку / выгулу", "Приучена к лотку / выгулу"),
        "child_friendly": ("Дружит с детьми", "Дружит с детьми"),
        "animal_friendly": ("Дружит с другими животными", "Дружит с другими животными"),
    },
}


def resolve_catalog_label(*, kind: str, slug: str, sex: str | None, fallback: str) -> str:
    forms = _CATALOG_LABELS_BY_KIND.get(kind, {}).get(slug)
    if forms is None:
        return fallback
    male, female = forms
    if male == female:
        return male
    normalized = (sex or "").strip().lower()
    if normalized == "male":
        return male
    if normalized == "female":
        return female
    return fallback
