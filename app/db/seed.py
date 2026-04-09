from sqlalchemy.orm import Session

from app.models.animal import Animal, AnimalStatus


def seed_animals_if_empty(db: Session) -> None:
    has_any = db.query(Animal.id).first()
    if has_any:
        return

    demo_animals = [
        Animal(
            name="Боня",
            sex="female",
            age_months=18,
            short_story="Спокойная и ласковая собака, ищет дом.",
            health_info="Привита, стерилизована.",
            character_info="Дружелюбная, любит прогулки.",
            location_city="Москва",
            is_urgent=False,
            status=AnimalStatus.LOOKING_FOR_HOME.value,
            help_options="Корм, прогулки, финансовая помощь.",
        ),
        Animal(
            name="Ричи",
            sex="male",
            age_months=8,
            short_story="Щенок после лечения, нужен куратор.",
            health_info="Проходит восстановление после операции.",
            character_info="Активный, контактный.",
            location_city="Санкт-Петербург",
            is_urgent=True,
            status=AnimalStatus.ON_TREATMENT.value,
            help_options="Оплата лечения, передержка.",
        ),
        Animal(
            name="Маруся",
            sex="female",
            age_months=36,
            short_story="Кошка из приюта, готова к переезду.",
            health_info="Здорова, обработана от паразитов.",
            character_info="Спокойная, приучена к лотку.",
            location_city="Казань",
            is_urgent=False,
            status=AnimalStatus.IN_SHELTER.value,
            help_options="Пиар, поиск дома, корм.",
        ),
        Animal(
            name="Грей",
            sex="male",
            age_months=24,
            short_story="Требуется срочная помощь в лечении.",
            health_info="Подозрение на перелом лапы.",
            character_info="Осторожный, но добрый.",
            location_city="Екатеринбург",
            is_urgent=True,
            status=AnimalStatus.ON_TREATMENT.value,
            help_options="Транспортировка в клинику, оплата рентгена.",
        ),
    ]

    db.add_all(demo_animals)
    db.commit()
