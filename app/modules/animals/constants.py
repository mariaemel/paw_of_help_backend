SPECIES_LABELS = {"cat": "Кошка", "dog": "Собака", "other": "Другое"}

AGE_GROUPS = [
    {"id": "baby", "label": "Малыш (до 1 года)", "max_months": 11},
    {"id": "adult", "label": "Взрослый (от 1 года)", "min_months": 12},
]

FEATURE_FILTERS = [
    {"id": "vaccinated", "field": "is_vaccinated", "label": "Привит"},
    {"id": "sterilized", "field": "is_sterilized", "label": "Стерилизован / кастрирован"},
    {"id": "litter_trained", "field": "is_litter_trained", "label": "Приучен к лотку / выгулу"},
    {"id": "child_friendly", "field": "is_child_friendly", "label": "Дружит с детьми"},
    {"id": "animal_friendly", "field": "is_animal_friendly", "label": "Дружит с другими животными"},
    {"id": "health_issues", "field": "has_health_issues", "label": "Имеет особенности здоровья"},
]
