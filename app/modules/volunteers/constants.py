COMPETENCY_OPTIONS: list[dict[str, str]] = [
    {"id": "walk", "label": "Выгул / Уход"},
    {"id": "photo_video", "label": "Фото / Видеосъемка"},
    {"id": "foster", "label": "Передержка"},
    {"id": "texts_social", "label": "Тексты / Соцсети"},
    {"id": "manual", "label": "Помощь руками"},
    {"id": "auto", "label": "Автопомощь"},
    {"id": "medical", "label": "Медицинская помощь"},
]

EXPERIENCE_LEVEL_OPTIONS: list[dict[str, str]] = [
    {"id": "beginner", "label": "Новичок"},
    {"id": "experienced", "label": "Опытный"},
    {"id": "vet_education", "label": "Ветеринарное образование"},
]

ANIMAL_TYPE_FILTER_OPTIONS: list[dict[str, str]] = [
    {"id": "cat", "label": "Кошки"},
    {"id": "dog", "label": "Собаки"},
    {"id": "all", "label": "Все"},
]

COMPETENCY_SHORT_LABELS: dict[str, str] = {
    "walk": "Выгул",
    "photo_video": "Фото",
    "foster": "Передержка",
    "texts_social": "Тексты",
    "manual": "Руки",
    "auto": "Авто",
    "medical": "Мед.",
}

EXPERIENCE_LEVEL_LABELS: dict[str, str] = {x["id"]: x["label"] for x in EXPERIENCE_LEVEL_OPTIONS}
