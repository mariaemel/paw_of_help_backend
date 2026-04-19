import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.animal import Animal, AnimalPhoto, AnimalSpecies, AnimalStatus
from app.models.animal_catalog import AnimalCatalogAssignment, AnimalCatalogItem
from app.models.organization import Organization
from app.models.profile import VolunteerProfile, VolunteerReview
from app.models.volunteer_competency import VolunteerCompetencyAssignment, VolunteerCompetencyItem
from app.models.user import User, UserRole
from app.modules.volunteers.constants import COMPETENCY_OPTIONS

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SEED_ANIMAL_IMAGES_DIR = _REPO_ROOT / "seed_images" / "animals"

_DEMO_ANIMAL_PHOTOS: dict[str, list[tuple[str, bool]]] = {
    "Муся": [
        ("demo_animals/musya.png", True),
        ("demo_animals/musya_2.png", False),
    ],
    "Боня": [
        ("demo_animals/bonya.png", True),
    ],
    "Ричи": [
        ("demo_animals/richi.png", True),
        ("demo_animals/richi_2.png", False),
    ],
}


def _materialize_seed_animal_images() -> bool:
    if not (_SEED_ANIMAL_IMAGES_DIR / "musya.png").is_file():
        return False
    dest = Path(settings.media_dir) / "demo_animals"
    dest.mkdir(parents=True, exist_ok=True)
    for png in sorted(_SEED_ANIMAL_IMAGES_DIR.glob("*.png")):
        shutil.copy2(png, dest / png.name)
    return True


def _sync_demo_animal_photos(db: Session, animal: Animal, photos_ready: bool) -> None:
    paths = _DEMO_ANIMAL_PHOTOS.get(animal.name)
    if not paths or not photos_ready:
        return
    db.query(AnimalPhoto).filter(
        AnimalPhoto.animal_id == animal.id,
        AnimalPhoto.file_path.like("demo_animals/%"),
    ).delete(synchronize_session=False)
    for rel_path, is_primary in paths:
        db.add(AnimalPhoto(animal_id=animal.id, file_path=rel_path, is_primary=is_primary))


_CATALOG_ITEM_DEFS: tuple[tuple[str, str, str, int], ...] = (
    ("health_care", "vaccinated", "Привит(а)", 10),
    ("health_care", "sterilized", "Стерилизован(а) / кастрирован(а)", 20),
    ("health_care", "vaccinated_full", "Комплексно привит(а)", 30),
    ("health_care", "dewormed", "Обработан(а) от паразитов", 40),
    ("character", "calm", "Спокойный(ая)", 10),
    ("character", "affectionate", "Ласковый(ая)", 20),
    ("character", "afraid_loud", "Боится громких звуков", 30),
    ("character", "friendly", "Дружелюбный(ая)", 40),
    ("character", "active", "Активный(ая)", 50),
    ("character", "contact", "Контактный(ая)", 60),
    ("character", "litter_trained", "Приучен к лотку / выгулу", 70),
    ("character", "child_friendly", "Дружит с детьми", 80),
    ("character", "animal_friendly", "Дружит с другими животными", 90),
)


def ensure_animal_catalog_items(db: Session) -> None:
    for kind, slug, label, sort_order in _CATALOG_ITEM_DEFS:
        exists = (
            db.query(AnimalCatalogItem.id)
            .filter(AnimalCatalogItem.kind == kind, AnimalCatalogItem.slug == slug)
            .first()
        )
        if exists:
            continue
        db.add(
            AnimalCatalogItem(
                kind=kind,
                slug=slug,
                label=label,
                sort_order=sort_order,
                is_active=True,
                keywords_json=None,
            )
        )


def ensure_volunteer_competency_items(db: Session) -> None:
    for idx, opt in enumerate(COMPETENCY_OPTIONS, start=1):
        slug = opt["id"]
        exists_row = db.query(VolunteerCompetencyItem.id).filter(VolunteerCompetencyItem.slug == slug).first()
        if exists_row:
            continue
        db.add(
            VolunteerCompetencyItem(
                slug=slug,
                label=opt["label"],
                sort_order=idx * 10,
                is_active=True,
            )
        )


@dataclass(frozen=True)
class DemoAnimalSeed:
    name: str
    use_second_org: bool
    species: str
    breed: str
    sex: str
    age_months: int
    full_description: str | None
    health_features: str | None
    treatment_required: str | None
    location_city: str | None
    is_urgent: bool
    urgent_needs_text: str | None
    status: str
    help_options: str | None
    catalog_keys: tuple[tuple[str, str], ...]


DEMO_ANIMALS: tuple[DemoAnimalSeed, ...] = (
    DemoAnimalSeed(
        name="Муся",
        use_second_org=False,
        species=AnimalSpecies.CAT.value,
        breed="Метис",
        sex="female",
        age_months=24,
        full_description="Мусю нашли зимой, сейчас она полностью готова к пристройству.",
        health_features="Хроническая почечная недостаточность начальной стадии.",
        treatment_required="Пониженное содержание фосфора в корме, осмотр у врача 1 раз в полгода.",
        location_city="Москва",
        is_urgent=True,
        urgent_needs_text="Срочный сбор: нужен лечебный корм.",
        status=AnimalStatus.LOOKING_FOR_HOME.value,
        help_options="Корм, финансовая помощь, репост.",
        catalog_keys=(
            ("health_care", "sterilized"),
            ("health_care", "vaccinated_full"),
            ("health_care", "dewormed"),
            ("character", "calm"),
            ("character", "affectionate"),
            ("character", "afraid_loud"),
        ),
    ),
    DemoAnimalSeed(
        name="Боня",
        use_second_org=True,
        species=AnimalSpecies.DOG.value,
        breed="Метис",
        sex="female",
        age_months=18,
        full_description="Боня любит прогулки и хорошо ладит с людьми.",
        health_features=None,
        treatment_required=None,
        location_city="Санкт-Петербург",
        is_urgent=False,
        urgent_needs_text=None,
        status=AnimalStatus.LOOKING_FOR_HOME.value,
        help_options="Корм, прогулки, автопомощь.",
        catalog_keys=(
            ("health_care", "vaccinated"),
            ("health_care", "sterilized"),
            ("character", "friendly"),
            ("character", "active"),
            ("character", "animal_friendly"),
        ),
    ),
    DemoAnimalSeed(
        name="Ричи",
        use_second_org=False,
        species=AnimalSpecies.DOG.value,
        breed="Метис",
        sex="male",
        age_months=8,
        full_description="Ричи восстанавливается после операции и нуждается в передержке.",
        health_features="Период восстановления после операции.",
        treatment_required="Контроль у хирурга через 2 недели.",
        location_city="Москва",
        is_urgent=True,
        urgent_needs_text="Срочно нужна передержка и помощь транспортом.",
        status=AnimalStatus.ON_TREATMENT.value,
        help_options="Оплата лечения, передержка, автопомощь.",
        catalog_keys=(
            ("character", "active"),
            ("character", "contact"),
        ),
    ),
)


def _catalog_key_to_id(db: Session) -> dict[tuple[str, str], int]:
    rows = db.query(AnimalCatalogItem.id, AnimalCatalogItem.kind, AnimalCatalogItem.slug).all()
    return {(r.kind, r.slug): int(r.id) for r in rows}


def _volunteer_competency_slug_to_id(db: Session) -> dict[str, int]:
    rows = db.query(VolunteerCompetencyItem.id, VolunteerCompetencyItem.slug).all()
    return {r.slug: int(r.id) for r in rows}


def _set_volunteer_competency_slugs(db: Session, profile_id: int, slugs: tuple[str, ...] | list[str]) -> None:
    db.query(VolunteerCompetencyAssignment).filter(
        VolunteerCompetencyAssignment.volunteer_profile_id == profile_id
    ).delete(synchronize_session=False)
    slug_to_id = _volunteer_competency_slug_to_id(db)
    seen: set[str] = set()
    for s in slugs:
        if s in seen:
            continue
        seen.add(s)
        cid = slug_to_id.get(s)
        if cid is None:
            continue
        db.add(VolunteerCompetencyAssignment(volunteer_profile_id=profile_id, competency_item_id=cid))


def _set_animal_catalog_links(db: Session, animal_id: int, keys: tuple[tuple[str, str], ...]) -> None:
    db.query(AnimalCatalogAssignment).filter(AnimalCatalogAssignment.animal_id == animal_id).delete()
    key_to_id = _catalog_key_to_id(db)
    for kind, slug in keys:
        cid = key_to_id.get((kind, slug))
        if cid is None:
            continue
        db.add(AnimalCatalogAssignment(animal_id=animal_id, catalog_item_id=cid))


def ensure_demo_animals(db: Session, org1: Organization, org2: Organization) -> None:
    photos_ready = _materialize_seed_animal_images()

    for spec in DEMO_ANIMALS:
        org = org2 if spec.use_second_org else org1
        animal = db.query(Animal).filter(Animal.name == spec.name).first()
        common = {
            "organization_id": org.id,
            "species": spec.species,
            "breed": spec.breed,
            "sex": spec.sex,
            "age_months": spec.age_months,
            "full_description": spec.full_description,
            "health_features": spec.health_features,
            "treatment_required": spec.treatment_required,
            "location_city": spec.location_city,
            "is_urgent": spec.is_urgent,
            "urgent_needs_text": spec.urgent_needs_text,
            "status": spec.status,
            "help_options": spec.help_options,
        }
        if animal is None:
            animal = Animal(name=spec.name, **common)
            db.add(animal)
            db.flush()
        else:
            for key, value in common.items():
                setattr(animal, key, value)
        _set_animal_catalog_links(db, animal.id, spec.catalog_keys)
        _sync_demo_animal_photos(db, animal, photos_ready)


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

    ensure_animal_catalog_items(db)
    ensure_volunteer_competency_items(db)
    ensure_demo_animals(db, org1, org2)

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
                    about_me=(
                        "Занимаюсь волонтёрством более 3 лет. Есть автомобиль для перевозки животных, "
                        "могу помочь с фотосъемкой и выгулом. Периодически беру на передержку."
                    ),
                    availability="Сб-Вс: с 10:00 до 20:00. Пн-Пт: только вечером после 19:00.",
                    location_city="Екатеринбург",
                    travel_radius_km=30,
                    animal_types_json=json.dumps(["cat", "dog"], ensure_ascii=False),
                    experience_level="experienced",
                    rating=4.9,
                    completed_tasks_count=24,
                    is_available=True,
                    latitude=56.8389,
                    longitude=60.6057,
                ),
                VolunteerProfile(
                    user_id=v2.id,
                    about_me="Помогаю с передержкой кошек по выходным.",
                    availability="Выходные",
                    location_city="Санкт-Петербург",
                    travel_radius_km=40,
                    animal_types_json=json.dumps(["cat"], ensure_ascii=False),
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
        vp1 = db.query(VolunteerProfile).filter(VolunteerProfile.user_id == v1.id).one()
        vp2 = db.query(VolunteerProfile).filter(VolunteerProfile.user_id == v2.id).one()
        _set_volunteer_competency_slugs(db, vp1.id, ("auto", "photo_video", "walk"))
        _set_volunteer_competency_slugs(db, vp2.id, ("foster", "walk", "manual"))
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
    ensure_volunteer_competency_items(db)
    v1 = db.query(User).filter(User.email == "volunteer1@example.com").first()
    if v1 and v1.volunteer_profile:
        p = v1.volunteer_profile
        if not p.competency_assignments:
            _set_volunteer_competency_slugs(db, p.id, ("auto", "photo_video", "walk"))
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
        if not p2.competency_assignments:
            _set_volunteer_competency_slugs(db, p2.id, ("foster", "walk", "manual"))
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


if __name__ == "__main__":
    from app.db.base import Base
    from app.db.migrate import ensure_sqlite_schema
    from app.db.session import SessionLocal, engine

    import app.models

    ensure_sqlite_schema(engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        seed_demo_data_if_empty(session)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    print("seed_demo_data_if_empty: OK")
