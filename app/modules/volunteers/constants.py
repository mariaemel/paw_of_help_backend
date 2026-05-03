COMPETENCY_OPTIONS: list[dict[str, str]] = [
    {"id": "walk", "label": "Выгул / уход"},
    {"id": "photo_video", "label": "Фото / видео"},
    {"id": "foster", "label": "Передержка"},
    {"id": "texts_social", "label": "SMM / тексты"},
    {"id": "manual", "label": "Помощь в приюте"},
    {"id": "auto", "label": "Автопомощь"},
    {"id": "medical", "label": "Медицина"},
    {"id": "rescue", "label": "Спасение"},
    {"id": "events", "label": "Мероприятия"},
    {"id": "fundraising", "label": "Фандрайзинг"},
    {"id": "other", "label": "Другое"},
]

COMPETENCY_PROFILE_TAG_BY_SLUG: dict[str, str] = {x["id"]: x["label"] for x in COMPETENCY_OPTIONS}

EXPERIENCE_LEVEL_OPTIONS: list[dict[str, str]] = [
    {"id": "beginner", "label": "Новичок"},
    {"id": "experienced", "label": "Опытный"},
    {"id": "vet_education", "label": "Ветеринарное образование"},
]

ANIMAL_TYPE_FILTER_OPTIONS: list[dict[str, str]] = [
    {"id": "cat", "label": "Кошки"},
    {"id": "dog", "label": "Собаки"},
    {"id": "bird", "label": "Птицы"},
    {"id": "rodent", "label": "Грызуны"},
    {"id": "exotic", "label": "Экзотические животные"},
    {"id": "large_dog", "label": "Крупные собаки"},
    {"id": "young", "label": "Щенки / котята"},
    {"id": "special_needs", "label": "Животные с инвалидностью / медуход"},
    {"id": "behavior", "label": "Сложное поведение"},
    {"id": "all", "label": "Все"},
]

COMPETENCY_SHORT_LABELS: dict[str, str] = {
    "walk": "Выгул",
    "photo_video": "Фото",
    "foster": "Передержка",
    "texts_social": "SMM",
    "manual": "Приют",
    "auto": "Авто",
    "medical": "Мед.",
    "rescue": "Спасение",
    "events": "Ивенты",
    "fundraising": "Фандрайзинг",
    "other": "Другое",
}

EXPERIENCE_LEVEL_LABELS: dict[str, str] = {x["id"]: x["label"] for x in EXPERIENCE_LEVEL_OPTIONS}

HELP_FORMAT_LABELS: dict[str, str] = {
    "one_time": "Разовая помощь",
    "recurring": "Регулярная помощь",
}

TRAVEL_AREA_MODE_LABELS: dict[str, str] = {
    "neighborhood": "В своём районе",
    "radius_10km": "До 10 км от меня",
    "whole_city": "По всему городу",
    "region": "Готов выезжать за город",
}

ALLOWED_TRAVEL_AREA_MODES = frozenset(TRAVEL_AREA_MODE_LABELS.keys())
ALLOWED_HELP_FORMATS = frozenset(HELP_FORMAT_LABELS.keys())

WEEKDAY_ORDER: tuple[str, ...] = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

WEEKDAY_LABEL_RU: dict[str, str] = {
    "monday": "Понедельник",
    "tuesday": "Вторник",
    "wednesday": "Среда",
    "thursday": "Четверг",
    "friday": "Пятница",
    "saturday": "Суббота",
    "sunday": "Воскресенье",
}

KNOWLEDGE_CATEGORY_LABELS: dict[str, str] = {
    "care": "Уход",
    "first_aid": "Первая помощь",
    "legal": "Юридическое",
    "education": "Обучение",
}
