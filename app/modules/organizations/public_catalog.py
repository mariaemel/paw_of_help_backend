WARD_STATUS_PUBLIC_LABELS: dict[str, str] = {
    "looking_for_home": "Ищет дом",
    "on_treatment": "На лечении",
    "looking_for_foster": "Ищет передержку",
    "in_shelter": "В приюте",
    "adopted": "Пристроена",
    "archived": "Архив",
}


DEFAULT_HELP_SECTIONS: tuple[dict[str, str], ...] = (
    {
        "kind": "financial",
        "title": "Финансовая помощь",
        "description": (
            "Пожертвования на корм, лечение и содержание подопечных. "
            "Реквизиты и сборы указаны во вкладке «О нас» и в активных заявках."
        ),
        "primary_action": "help",
    },
    {
        "kind": "volunteering",
        "title": "Волонтёрство",
        "description": "Выгул, уход за животными, помощь на мероприятиях и в приюте.",
        "primary_action": "respond",
    },
    {
        "kind": "foster",
        "title": "Передержка",
        "description": "Временная домашняя передержка для животных, которым нужен покой после лечения.",
        "primary_action": "contact",
    },
    {
        "kind": "items",
        "title": "Помощь вещами",
        "description": "Корм, медикаменты, поводки, лежаки и расходники для содержания.",
        "primary_action": "help",
    },
    {
        "kind": "auto",
        "title": "Автопомощь",
        "description": "Перевозка животных в клиники, между передержками и на акции помощи.",
        "primary_action": "respond",
    },
)
