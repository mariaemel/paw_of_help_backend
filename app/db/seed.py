import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.animal import Animal, AnimalSpecies, AnimalStatus
from app.models.organization import Organization
from app.models.profile import VolunteerProfile, VolunteerReview
from app.models.user import User, UserRole


def seed_demo_data_if_empty(db: Session) -> None:
    orgs = db.query(Organization).order_by(Organization.id.asc()).all()
    if len(orgs) < 2:
        org1 = Organization(
            name="Благотворительный фонд «Верный друг»",
            city="Москва",
            address="Москва, ул. Добрых дел, 10",
            specialization="both",
            needs_json=json.dumps(["urgent", "volunteers", "auto"], ensure_ascii=False),
            wards_count=150,
            adopted_yearly_count=47,
            description="Фонд помощи животным.",
            latitude=55.7558,
            longitude=37.6173,
        )
        org2 = Organization(
            name="Приют «Теплые лапы»",
            city="Санкт-Петербург",
            address="Санкт-Петербург, пр. Заботы, 5",
            specialization="cat",
            needs_json=json.dumps(["foster", "items"], ensure_ascii=False),
            wards_count=93,
            adopted_yearly_count=28,
            description="Приют для кошек и котят.",
            latitude=59.9343,
            longitude=30.3351,
        )
        db.add_all([org1, org2])
        db.flush()
        orgs = [org1, org2]

    org1 = orgs[0]
    org2 = orgs[1] if len(orgs) > 1 else orgs[0]

    if not db.query(Animal.id).first():
        demo_animals = [
            Animal(
                organization_id=org1.id,
                name="Муся",
                species=AnimalSpecies.CAT.value,
                breed="Метис",
                sex="female",
                age_months=24,
                short_story="Спокойная кошка, ищет дом.",
                full_description="Мусю нашли зимой, сейчас она полностью готова к пристройству.",
                health_checklist_json=json.dumps(
                    ["Стерилизована", "Комплексно привита", "Обработана от паразитов"],
                    ensure_ascii=False,
                ),
                health_features="Хроническая почечная недостаточность начальной стадии.",
                treatment_required="Пониженное содержание фосфора в корме, осмотр у врача 1 раз в полгода.",
                character_tags_json=json.dumps(
                    ["Спокойная", "Ласковая", "Боится громких звуков"],
                    ensure_ascii=False,
                ),
                location_city="Москва",
                is_urgent=True,
                urgent_needs_text="Срочный сбор: нужен лечебный корм.",
                status=AnimalStatus.LOOKING_FOR_HOME.value,
                help_options="Корм, финансовая помощь, репост.",
                is_vaccinated=True,
                is_sterilized=True,
                is_litter_trained=True,
                is_child_friendly=True,
                is_animal_friendly=True,
                has_health_issues=True,
            ),
            Animal(
                organization_id=org2.id,
                name="Боня",
                species=AnimalSpecies.DOG.value,
                breed="Метис",
                sex="female",
                age_months=18,
                short_story="Ласковая собака, ищет дом.",
                full_description="Боня любит прогулки и хорошо ладит с людьми.",
                health_checklist_json=json.dumps(["Привита", "Стерилизована"], ensure_ascii=False),
                character_tags_json=json.dumps(["Дружелюбная", "Активная"], ensure_ascii=False),
                location_city="Санкт-Петербург",
                is_urgent=False,
                status=AnimalStatus.LOOKING_FOR_HOME.value,
                help_options="Корм, прогулки, автопомощь.",
                is_vaccinated=True,
                is_sterilized=True,
                is_child_friendly=True,
                is_animal_friendly=True,
            ),
            Animal(
                organization_id=org1.id,
                name="Ричи",
                species=AnimalSpecies.DOG.value,
                breed="Метис",
                sex="male",
                age_months=8,
                short_story="Щенок после лечения, нужен куратор.",
                full_description="Ричи восстанавливается после операции и нуждается в передержке.",
                health_features="Период восстановления после операции.",
                treatment_required="Контроль у хирурга через 2 недели.",
                character_tags_json=json.dumps(["Активный", "Контактный"], ensure_ascii=False),
                location_city="Москва",
                is_urgent=True,
                urgent_needs_text="Срочно нужна передержка и помощь транспортом.",
                status=AnimalStatus.ON_TREATMENT.value,
                help_options="Оплата лечения, передержка, автопомощь.",
                has_health_issues=True,
            ),
        ]
        db.add_all(demo_animals)

    if not db.query(VolunteerProfile.id).first():
        v1 = User(
            email="volunteer1@example.com",
            phone="+79990000001",
            password_hash="seed-password-hash",
            full_name="Анна Смирнова",
            role=UserRole.VOLUNTEER,
            is_email_verified=True,
        )
        v2 = User(
            email="volunteer2@example.com",
            phone="+79990000002",
            password_hash="seed-password-hash",
            full_name="Илья Петров",
            role=UserRole.VOLUNTEER,
            is_email_verified=True,
        )
        db.add_all([v1, v2])
        db.flush()
        db.add_all(
            [
                VolunteerProfile(
                    user_id=v1.id,
                    skills="Авто, фотосъемка, выгул",
                    experience="Опытный волонтёр",
                    about_me=(
                        "Занимаюсь волонтёрством более 3 лет. Есть автомобиль для перевозки животных, "
                        "могу помочь с фотосъемкой и выгулом. Периодически беру на передержку."
                    ),
                    availability="Сб-Вс: с 10:00 до 20:00. Пн-Пт: только вечером после 19:00.",
                    location_city="Екатеринбург",
                    travel_radius_km=30,
                    preferred_help_format="Оффлайн",
                    animal_categories="Кошки, собаки",
                    animal_types_json=json.dumps(["cat", "dog"], ensure_ascii=False),
                    competencies_json=json.dumps(
                        ["auto", "photo_video", "walk"], ensure_ascii=False
                    ),
                    experience_level="experienced",
                    rating=4.9,
                    completed_tasks_count=24,
                    is_available=True,
                    latitude=56.8389,
                    longitude=60.6057,
                ),
                VolunteerProfile(
                    user_id=v2.id,
                    skills="Передержка, уход",
                    experience="Новичок в приюте, но ответственный.",
                    about_me="Помогаю с передержкой кошек по выходным.",
                    availability="Выходные",
                    location_city="Санкт-Петербург",
                    travel_radius_km=40,
                    preferred_help_format="Смешанный",
                    animal_categories="Кошки",
                    animal_types_json=json.dumps(["cat"], ensure_ascii=False),
                    competencies_json=json.dumps(["foster", "walk", "manual"], ensure_ascii=False),
                    experience_level="beginner",
                    rating=4.5,
                    completed_tasks_count=15,
                    is_available=True,
                    latitude=59.9343,
                    longitude=30.3351,
                ),
            ]
        )
        db.flush()
        db.add(
            VolunteerReview(
                volunteer_user_id=v1.id,
                author_name="Приют «Верный»",
                author_avatar_path=None,
                review_date=datetime(2026, 4, 12, 12, 0, 0),
                rating=5,
                text="Анна оперативно помогла с транспортом и сделала отличные фото для соцсетей.",
            )
        )

    enrich_demo_volunteers(db)

    db.commit()


def enrich_demo_volunteers(db: Session) -> None:
    """Заполняет новые поля демо-волонтёров, если база уже существовала без них."""
    v1 = db.query(User).filter(User.email == "volunteer1@example.com").first()
    if v1 and v1.volunteer_profile:
        p = v1.volunteer_profile
        if p.competencies_json is None:
            p.competencies_json = json.dumps(["auto", "photo_video", "walk"], ensure_ascii=False)
        if p.animal_types_json is None:
            p.animal_types_json = json.dumps(["cat", "dog"], ensure_ascii=False)
        if p.experience_level is None:
            p.experience_level = "experienced"
        if not p.about_me:
            p.about_me = (
                "Занимаюсь волонтёрством более 3 лет. Есть автомобиль для перевозки животных."
            )
        if p.rating is None or p.rating == 0:
            p.rating = 4.9
        if not p.completed_tasks_count:
            p.completed_tasks_count = 24
        if p.latitude is None:
            p.latitude = 56.8389
        if p.longitude is None:
            p.longitude = 60.6057
        if p.location_city is None:
            p.location_city = "Екатеринбург"
        if p.travel_radius_km is None:
            p.travel_radius_km = 30
        if v1.full_name == "Анна Иванова":
            v1.full_name = "Анна Смирнова"

    v2 = db.query(User).filter(User.email == "volunteer2@example.com").first()
    if v2 and v2.volunteer_profile:
        p2 = v2.volunteer_profile
        if p2.competencies_json is None:
            p2.competencies_json = json.dumps(["foster", "walk", "manual"], ensure_ascii=False)
        if p2.animal_types_json is None:
            p2.animal_types_json = json.dumps(["cat"], ensure_ascii=False)
        if p2.experience_level is None:
            p2.experience_level = "beginner"
        if p2.rating is None or p2.rating == 0:
            p2.rating = 4.5
        if not p2.completed_tasks_count:
            p2.completed_tasks_count = 15
        if p2.latitude is None:
            p2.latitude = 59.9343
        if p2.longitude is None:
            p2.longitude = 30.3351

    if not db.query(VolunteerReview.id).first() and v1:
        db.add(
            VolunteerReview(
                volunteer_user_id=v1.id,
                author_name="Приют «Верный»",
                author_avatar_path=None,
                review_date=datetime(2026, 4, 12, 12, 0, 0),
                rating=5,
                text="Анна оперативно помогла с транспортом и сделала отличные фото для соцсетей.",
            )
        )
