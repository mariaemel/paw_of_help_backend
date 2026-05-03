import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.security import hash_password
from app.models.adoption_application import AdoptionApplicationStatus, AnimalAdoptionApplication
from app.models.animal import Animal, AnimalPhoto, AnimalSpecies, AnimalStatus
from app.models.animal_catalog import AnimalCatalogAssignment, AnimalCatalogItem
from app.models.event import Event
from app.models.help_request import HelpRequest
from app.models.volunteer_help_response import VolunteerHelpResponse, VolunteerHelpResponseStatus
from app.models.volunteer_help_response_report import VolunteerHelpResponseReport
from app.models.knowledge import KnowledgeArticle
from app.models.organization import Organization
from app.models.organization_home_story import OrganizationHomeStory
from app.models.organization_report import OrganizationReport
from app.models.profile import UserProfile, VolunteerProfile
from app.models.volunteer_competency import VolunteerCompetencyAssignment, VolunteerCompetencyItem
from app.models.user import User, UserRole
from app.modules.volunteers.constants import COMPETENCY_OPTIONS

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SEED_ANIMAL_IMAGES_DIR = _REPO_ROOT / "seed_images" / "animals"
_SEED_URGENT_IMAGES_DIR = _REPO_ROOT / "seed_images" / "urgent"

_DEMO_ANIMAL_PHOTOS: dict[str, list[tuple[str, bool]]] = {
    "Муся": [("demo_animals/musya.png", True)],
    "Маруся": [("demo_animals/marusya.png", True)],
    "Боня": [("demo_animals/bonya.png", True)],
    "Ричи": [("demo_animals/richi.png", True)],
    "Грей": [("demo_animals/grey.png", True)],
}


def _materialize_seed_animal_images() -> bool:
    required = ("musya.png", "marusya.png", "bonya.png", "richi.png", "grey.png")
    for name in required:
        if not (_SEED_ANIMAL_IMAGES_DIR / name).is_file():
            return False
    dest = Path(settings.media_dir) / "demo_animals"
    dest.mkdir(parents=True, exist_ok=True)
    for name in required:
        shutil.copy2(_SEED_ANIMAL_IMAGES_DIR / name, dest / name)
    return True


def _materialize_seed_urgent_images() -> bool:
    required = ("kittens_basement.png",)
    for name in required:
        if not (_SEED_URGENT_IMAGES_DIR / name).is_file():
            return False
    dest = Path(settings.media_dir) / "demo_urgent"
    dest.mkdir(parents=True, exist_ok=True)
    for name in required:
        shutil.copy2(_SEED_URGENT_IMAGES_DIR / name, dest / name)
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
        row = db.query(VolunteerCompetencyItem).filter(VolunteerCompetencyItem.slug == slug).first()
        if row is None:
            db.add(
                VolunteerCompetencyItem(
                    slug=slug,
                    label=opt["label"],
                    sort_order=idx * 10,
                    is_active=True,
                )
            )
        else:
            row.label = opt["label"]
            row.sort_order = idx * 10


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
        full_description=(
            "Мусю нашли зимой, сейчас проходит восстановление после операции на лапе "
            "и нуждается в поддержке до полного выздоровления."
        ),
        health_features="Период восстановления после операции.",
        treatment_required="Контроль у хирурга, ограниченная активность до заживления.",
        location_city="Екатеринбург",
        is_urgent=True,
        urgent_needs_text="Нужна операция на лапе и поддержка восстановления.",
        status=AnimalStatus.ON_TREATMENT.value,
        help_options="Операция на лапе, финансовая помощь, репост.",
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
        name="Маруся",
        use_second_org=False,
        species=AnimalSpecies.CAT.value,
        breed="Метис",
        sex="female",
        age_months=36,
        full_description="Маруся — спокойная и внимательная кошка, любит общение и спокойную обстановку.",
        health_features=None,
        treatment_required=None,
        location_city="Екатеринбург",
        is_urgent=False,
        urgent_needs_text=None,
        status=AnimalStatus.LOOKING_FOR_HOME.value,
        help_options="Корм, передержка на время отпуска хозяина.",
        catalog_keys=(
            ("health_care", "vaccinated"),
            ("health_care", "sterilized"),
            ("character", "calm"),
            ("character", "affectionate"),
            ("character", "contact"),
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
        location_city="Екатеринбург",
        is_urgent=True,
        urgent_needs_text="Срочно нужна передержка и помощь транспортом.",
        status=AnimalStatus.ON_TREATMENT.value,
        help_options="Оплата лечения, передержка, автопомощь.",
        catalog_keys=(
            ("character", "active"),
            ("character", "contact"),
        ),
    ),
    DemoAnimalSeed(
        name="Грей",
        use_second_org=True,
        species=AnimalSpecies.DOG.value,
        breed="Метис",
        sex="male",
        age_months=30,
        full_description="Грей активный и дружелюбный, хорошо переносит прогулки и контакт с людьми.",
        health_features=None,
        treatment_required=None,
        location_city="Санкт-Петербург",
        is_urgent=False,
        urgent_needs_text=None,
        status=AnimalStatus.LOOKING_FOR_HOME.value,
        help_options="Прогулки, корм, автопомощь на выставки.",
        catalog_keys=(
            ("health_care", "vaccinated"),
            ("health_care", "sterilized"),
            ("character", "friendly"),
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


def ensure_demo_knowledge_articles(db: Session, volunteer_user_id: int, organization_user_id: int) -> None:
    rows: list[tuple[str, str, str, int, bool, int, str]] = [
        (
            "Как кормить кошку в период адаптации",
            "Рацион, режим и объём порций для кошки в первые недели в новом доме.",
            "care",
            5,
            False,
            organization_user_id,
            "organization",
        ),
        (
            "Первая помощь при небольшом порезе лапы",
            "Что делать до визита к ветеринару и когда нужно срочно ехать в клинику.",
            "first_aid",
            7,
            True,
            volunteer_user_id,
            "volunteer",
        ),
        (
            "Юридические вопросы при пристройстве",
            "Какие документы подготовить и как корректно оформить передачу животного.",
            "legal",
            9,
            False,
            organization_user_id,
            "organization",
        ),
        (
            "Как правильно кормить кошку в период адаптации",
            "Рацион, режим и объём порций для кошки в первые недели в новом доме.",
            "care",
            5,
            False,
            volunteer_user_id,
            "volunteer",
        ),
    ]
    for title, summary, category, read_minutes, is_tip, uid, role in rows:
        article = (
            db.query(KnowledgeArticle)
            .filter(KnowledgeArticle.title == title, KnowledgeArticle.author_user_id == uid)
            .first()
        )
        if article is None:
            article = KnowledgeArticle(
                author_user_id=uid,
                owner_role=role,
                title=title,
                summary=summary,
                content=summary + " Подробное содержание статьи доступно в детальной карточке.",
                category=category,
                read_minutes=read_minutes,
                is_context_tip=is_tip,
                is_published=True,
                is_archived=False,
            )
            db.add(article)
        else:
            article.summary = summary
            article.category = category
            article.read_minutes = read_minutes
            article.is_context_tip = is_tip
            article.is_published = True
            article.is_archived = False


def ensure_demo_events(db: Session, org1: Organization, org2: Organization) -> None:
    starts = datetime(2026, 5, 3, 11, 0, 0)
    rows = [
        {
            "title": "Выставка питомцев «Найди друга»",
            "organization_id": org2.id,
            "summary": "Приходите познакомиться с подопечными и выбрать друга.",
            "description": (
                "Приходите познакомиться с нашими подопечными. Более 30 кошек и собак ищут дом. "
                "Специалисты расскажут, как правильно выбрать питомца и подготовить дом к его появлению."
            ),
            "city": "Екатеринбург",
            "address": "ул. Ленина, 52, ТЦ «Мегаполис», атриум",
            "format": "offline",
            "help_type": "adoption",
            "starts_at": starts,
            "ends_at": starts + timedelta(hours=6),
            "latitude": 56.8389,
            "longitude": 60.6057,
        },
        {
            "title": "Субботник в приюте «Теплые лапы»",
            "organization_id": org2.id,
            "summary": "Нужна помощь руками: уборка вольеров и сортировка кормов.",
            "description": "Открытый день помощи приюту: уборка, мелкий ремонт, сортировка гуманитарной помощи.",
            "city": "Санкт-Петербург",
            "address": "пр. Заботы, 5",
            "format": "offline",
            "help_type": "cleanup",
            "starts_at": starts + timedelta(days=7),
            "ends_at": starts + timedelta(days=7, hours=4),
            "latitude": 59.9343,
            "longitude": 30.3351,
        },
        {
            "title": "Онлайн-лекция: первая помощь животным",
            "organization_id": org1.id,
            "summary": "Практическая лекция для новичков и волонтёров.",
            "description": "Разберем типовые неотложные ситуации, как действовать до приезда в клинику.",
            "city": "Онлайн",
            "address": "Видеоконференция",
            "format": "online",
            "help_type": "education",
            "starts_at": starts + timedelta(days=3),
            "ends_at": starts + timedelta(days=3, hours=2),
            "latitude": None,
            "longitude": None,
        },
    ]
    for spec in rows:
        item = db.query(Event).filter(Event.title == spec["title"]).first()
        if item is None:
            item = Event(
                is_published=True,
                is_archived=False,
                **spec,
            )
            db.add(item)
            continue
        for key, value in spec.items():
            setattr(item, key, value)
        item.is_published = True
        item.is_archived = False


def ensure_demo_urgent_requests(db: Session, org1: Organization, org2: Organization) -> None:
    urgent_photos_ready = _materialize_seed_urgent_images()
    musya = db.query(Animal).filter(Animal.name == "Муся").first()
    richi = db.query(Animal).filter(Animal.name == "Ричи").first()
    marusya = db.query(Animal).filter(Animal.name == "Маруся").first()
    grey = db.query(Animal).filter(Animal.name == "Грей").first()
    rows = [
        {
            "organization_id": org1.id,
            "animal_id": musya.id if musya and musya.organization_id == org1.id else None,
            "title": "На операцию на лапу",
            "description": "Нужна операция на лапе и стационар, последующее восстановление.",
            "city": "Екатеринбург",
            "address": "Ветеринарная клиника, ул. Садовая, 12",
            "help_type": "medical",
            "is_urgent": True,
            "volunteer_needed": False,
            "volunteer_requirements": None,
            "volunteer_competencies_json": "[]",
            "target_amount": 15000.0,
            "collected_amount": 0.0,
            "deadline_at": datetime(2026, 5, 3, 23, 0, 0),
            "deadline_note": None,
            "media_path": None,
            "status": "open",
            "is_published": True,
            "is_archived": False,
        },
        {
            "organization_id": org1.id,
            "animal_id": marusya.id if marusya and marusya.organization_id == org1.id else None,
            "title": "На корм Gastrointestinal",
            "description": "Нужна поддержка расходами на диетический корм после обследования.",
            "city": "Екатеринбург",
            "address": None,
            "help_type": "food",
            "is_urgent": True,
            "volunteer_needed": False,
            "volunteer_requirements": None,
            "volunteer_competencies_json": "[]",
            "target_amount": 5000.0,
            "collected_amount": 0.0,
            "deadline_at": None,
            "deadline_note": None,
            "media_path": None,
            "status": "open",
            "is_published": True,
            "is_archived": False,
        },
        {
            "organization_id": org2.id,
            "animal_id": grey.id if grey and grey.organization_id == org2.id else None,
            "title": "Новые поводки и ошейники",
            "description": "Нужно закупить поводки и ошейники для выгула нескольких подопечных.",
            "city": "Санкт-Петербург",
            "address": None,
            "help_type": "financial",
            "is_urgent": False,
            "volunteer_needed": False,
            "volunteer_requirements": None,
            "volunteer_competencies_json": "[]",
            "target_amount": 3000.0,
            "collected_amount": 0.0,
            "deadline_at": None,
            "deadline_note": None,
            "media_path": None,
            "status": "open",
            "is_published": True,
            "is_archived": False,
        },
        {
            "organization_id": org1.id,
            "animal_id": richi.id if richi and richi.organization_id == org1.id else None,
            "title": "Пёс Рекс",
            "description": "Нужно отвезти крупную собаку из приюта в клинику на рентген.",
            "city": "Екатеринбург",
            "address": "ул. Белинского, 7",
            "help_type": "auto",
            "is_urgent": True,
            "volunteer_needed": True,
            "volunteer_requirements": "Нужен водитель с опытом перевозки животных.",
            "volunteer_competencies_json": json.dumps(["auto", "medical"], ensure_ascii=False),
            "target_amount": None,
            "collected_amount": 0.0,
            "deadline_at": datetime(2026, 5, 2, 15, 0, 0),
            "deadline_note": None,
            "media_path": None,
            "status": "open",
            "is_published": True,
            "is_archived": False,
        },
        {
            "organization_id": org2.id,
            "animal_id": None,
            "title": "Котята из подвала",
            "description": "У пятерых котят энтерит. Срочно нужен антибиотик и лечебный паштет.",
            "city": "Санкт-Петербург",
            "address": "Московский проспект, 80",
            "help_type": "medical",
            "is_urgent": True,
            "volunteer_needed": True,
            "volunteer_requirements": "Желателен опыт передержки и ухода за котятами.",
            "volunteer_competencies_json": json.dumps(["foster", "medical"], ensure_ascii=False),
            "target_amount": None,
            "collected_amount": 0.0,
            "deadline_at": datetime(2026, 5, 2, 10, 0, 0),
            "deadline_note": "Забрать нужно сегодня или завтра утром",
            "media_path": "demo_urgent/kittens_basement.png" if urgent_photos_ready else None,
            "status": "open",
            "is_published": True,
            "is_archived": False,
        },
    ]
    for spec in rows:
        item = db.query(HelpRequest).filter(HelpRequest.title == spec["title"]).first()
        if item is None:
            db.add(HelpRequest(**spec))
            continue
        for key, value in spec.items():
            setattr(item, key, value)

    _sync_help_demo_animal_links(db)


def _sync_help_demo_animal_links(db: Session) -> None:
    links: tuple[tuple[str, str], ...] = (
        ("На операцию на лапу", "Муся"),
        ("На корм Gastrointestinal", "Маруся"),
        ("Новые поводки и ошейники", "Грей"),
    )
    for title, animal_name in links:
        animal = db.query(Animal).filter(Animal.name == animal_name).first()
        hr = db.query(HelpRequest).filter(HelpRequest.title == title).first()
        if hr and animal and animal.organization_id == hr.organization_id:
            hr.animal_id = animal.id


_DEMO_LK_TRANSPORT_DESCRIPTION = (
    "Срочно нужна перевозка кота Василия в ветклинику на ул. Малышева. "
    "Требуется аккуратная транспортировка после операции"
)


def _migrate_lk_demo_help_request_titles(
    db: Session,
    volunteer_user_id: int,
    organization_id: int,
    demo_title: str,
    today_17: datetime,
    today_17b: datetime,
    may7_12: datetime,
) -> None:
    rows = (
        db.query(VolunteerHelpResponse)
        .options(joinedload(VolunteerHelpResponse.help_request))
        .filter(VolunteerHelpResponse.volunteer_user_id == volunteer_user_id)
        .all()
    )
    desc = _DEMO_LK_TRANSPORT_DESCRIPTION.strip()
    for row in rows:
        hr = row.help_request
        if hr is None or hr.organization_id != organization_id:
            continue
        if (hr.description or "").strip() != desc:
            continue
        if row.status == VolunteerHelpResponseStatus.PENDING.value:
            hr.title = demo_title
            hr.is_urgent = True
            hr.deadline_at = today_17
        elif row.status == VolunteerHelpResponseStatus.ACCEPTED.value:
            hr.title = demo_title
            hr.is_urgent = False
            hr.deadline_at = may7_12
        elif row.status == VolunteerHelpResponseStatus.COMPLETED.value:
            hr.title = demo_title
            hr.is_urgent = False
            hr.deadline_at = today_17
        elif row.status == VolunteerHelpResponseStatus.WITHDRAWN.value:
            hr.title = demo_title
            hr.is_urgent = False
            hr.deadline_at = today_17b


def ensure_demo_volunteer_help_responses_lk_mock(db: Session, org1: Organization) -> None:
    v = db.query(User).filter(User.email == "volunteer1@example.com").first()
    if v is None:
        return

    musya = (
        db.query(Animal)
        .filter(Animal.organization_id == org1.id, Animal.name == "Муся")
        .first()
    )
    demo_title = "Перевозка"
    now = datetime.utcnow()
    today_17 = now.replace(hour=17, minute=0, second=0, microsecond=0)
    today_17b = today_17 + timedelta(minutes=1)
    may7_12 = datetime(2026, 5, 7, 12, 0, 0)

    hr_specs: list[dict] = [
        {
            "description": _DEMO_LK_TRANSPORT_DESCRIPTION,
            "is_urgent": True,
            "deadline_at": today_17,
            "deadline_note": None,
        },
        {
            "description": _DEMO_LK_TRANSPORT_DESCRIPTION,
            "is_urgent": False,
            "deadline_at": may7_12,
            "deadline_note": None,
        },
        {
            "description": _DEMO_LK_TRANSPORT_DESCRIPTION,
            "is_urgent": False,
            "deadline_at": today_17,
            "deadline_note": None,
        },
        {
            "description": _DEMO_LK_TRANSPORT_DESCRIPTION,
            "is_urgent": False,
            "deadline_at": today_17b,
            "deadline_note": None,
        },
    ]

    response_statuses = (
        VolunteerHelpResponseStatus.PENDING.value,
        VolunteerHelpResponseStatus.ACCEPTED.value,
        VolunteerHelpResponseStatus.COMPLETED.value,
        VolunteerHelpResponseStatus.WITHDRAWN.value,
    )

    _migrate_lk_demo_help_request_titles(
        db, v.id, org1.id, demo_title, today_17, today_17b, may7_12
    )

    for spec, resp_status in zip(hr_specs, response_statuses):
        hr = (
            db.query(HelpRequest)
            .filter(
                HelpRequest.organization_id == org1.id,
                HelpRequest.title == demo_title,
                HelpRequest.help_type == "auto",
                HelpRequest.is_urgent.is_(spec["is_urgent"]),
                HelpRequest.deadline_at == spec["deadline_at"],
            )
            .first()
        )
        common_hr = {
            "organization_id": org1.id,
            "animal_id": musya.id if musya else None,
            "title": demo_title,
            "description": spec["description"],
            "city": "Екатеринбург",
            "address": "ул. Малышева, ветклиника",
            "help_type": "auto",
            "is_urgent": spec["is_urgent"],
            "volunteer_needed": True,
            "volunteer_requirements": "Нужен аккуратный перевозчик с опытом.",
            "volunteer_competencies_json": json.dumps(["auto"], ensure_ascii=False),
            "target_amount": None,
            "collected_amount": 0.0,
            "deadline_at": spec["deadline_at"],
            "deadline_note": spec["deadline_note"],
            "media_path": None,
            "status": "open",
            "is_published": True,
            "is_archived": False,
        }
        if hr is None:
            hr = HelpRequest(**common_hr)
            db.add(hr)
            db.flush()
        else:
            for key, value in common_hr.items():
                setattr(hr, key, value)

        row = (
            db.query(VolunteerHelpResponse)
            .filter(
                VolunteerHelpResponse.volunteer_user_id == v.id,
                VolunteerHelpResponse.help_request_id == hr.id,
            )
            .first()
        )
        msg = "Готов помочь с перевозкой, есть автомобиль и переноска."
        if row is None:
            row = VolunteerHelpResponse(
                volunteer_user_id=v.id,
                help_request_id=hr.id,
                status=resp_status,
                message=msg,
                created_at=now - timedelta(days=3),
                updated_at=now,
            )
            db.add(row)
            db.flush()
        else:
            row.status = resp_status
            row.message = msg
            row.updated_at = now

        if row.report is not None and resp_status != VolunteerHelpResponseStatus.COMPLETED.value:
            db.delete(row.report)
            db.flush()

        if resp_status == VolunteerHelpResponseStatus.COMPLETED.value:
            rep = row.report
            submitted = now - timedelta(days=1)
            accepted = now - timedelta(hours=3)
            body = (
                "Кота Василия доставили в клинику на ул. Малышева, врач принял, состояние стабильное."
            )
            if rep is None:
                db.add(
                    VolunteerHelpResponseReport(
                        volunteer_help_response_id=row.id,
                        body=body,
                        submitted_at=submitted,
                        org_accepted_at=accepted,
                        org_rejection_reason=None,
                    )
                )
            else:
                rep.body = body
                rep.submitted_at = submitted
                rep.org_accepted_at = accepted
                rep.org_rejection_reason = None


def sync_demo_adoption_applications_for_profile_mock(db: Session) -> None:
    u = db.query(User).filter(User.email == "user_demo@example.com").first()
    if u is None:
        return

    targets: list[tuple[str, str]] = [
        (
            "Муся",
            "Здравствуйте! Готова обсудить условия и приехать на знакомство с Мусей.",
        ),
        (
            "Маруся",
            "Маруся понравилась по описанию, есть подходящее пространство в квартире.",
        ),
    ]

    for aname, message in targets:
        animal = db.query(Animal).filter(Animal.name == aname).first()
        if animal is None:
            continue
        row = (
            db.query(AnimalAdoptionApplication)
            .filter(
                AnimalAdoptionApplication.user_id == u.id,
                AnimalAdoptionApplication.animal_id == animal.id,
            )
            .first()
        )
        ts = datetime.utcnow() - timedelta(days=1)
        if row is None:
            db.add(
                AnimalAdoptionApplication(
                    user_id=u.id,
                    animal_id=animal.id,
                    status=AdoptionApplicationStatus.PENDING_REVIEW.value,
                    message=message,
                    created_at=ts,
                    updated_at=ts,
                )
            )
        else:
            row.status = AdoptionApplicationStatus.PENDING_REVIEW.value
            row.message = message
            row.updated_at = datetime.utcnow()


_DEMO_LOGIN_PASSWORD_PLAIN = "demo12345"


def sync_demo_accounts_password(db: Session) -> None:
    emails = (
        "user_demo@example.com",
        "user_demo2@example.com",
        "volunteer1@example.com",
        "volunteer2@example.com",
        "org1@example.com",
        "org2@example.com",
    )
    h = hash_password(_DEMO_LOGIN_PASSWORD_PLAIN)
    for mail in emails:
        u = db.query(User).filter(User.email == mail).first()
        if u is not None:
            u.password_hash = h


def _ensure_demo_user_with_profile(
    db: Session,
    *,
    email: str,
    phone: str,
    full_name: str,
    bio: str,
    password_hash: str,
) -> User:
    u = db.query(User).filter(User.email == email).first()
    if u is None:
        u = User(
            email=email,
            phone=phone,
            password_hash=password_hash,
            full_name=full_name,
            role=UserRole.USER,
            is_email_verified=True,
            personal_data_consent_at=datetime.utcnow(),
        )
        db.add(u)
        db.flush()
        db.add(UserProfile(user_id=u.id, bio=bio))
    else:
        if u.user_profile is None:
            db.add(UserProfile(user_id=u.id, bio=bio))
        elif u.user_profile.bio is None and bio:
            u.user_profile.bio = bio
    return u


def ensure_demo_plain_users_and_adoption_applications(db: Session) -> None:
    ph = hash_password(_DEMO_LOGIN_PASSWORD_PLAIN)
    _ensure_demo_user_with_profile(
        db,
        email="user_demo@example.com",
        phone="+79990001001",
        full_name="Мария Козлова",
        bio="Ищу кошку для дома без других животных, есть опыт ухода.",
        password_hash=ph,
    )
    _ensure_demo_user_with_profile(
        db,
        email="user_demo2@example.com",
        phone="+79990001002",
        full_name="Игорь Васильев",
        bio="Планируем пристройство собаки, живём в доме с участком.",
        password_hash=ph,
    )

    animals = {
        row.name: row
        for row in db.query(Animal).filter(Animal.name.in_(["Муся", "Маруся", "Ричи", "Боня", "Грей"])).all()
    }

    specs: list[tuple[str, str, str, AdoptionApplicationStatus]] = [
        (
            "user_demo@example.com",
            "Муся",
            "Здравствуйте! Готова обсудить условия и приехать на знакомство.",
            AdoptionApplicationStatus.PENDING_REVIEW,
        ),
        (
            "user_demo@example.com",
            "Маруся",
            "Маруся понравилась по описанию, есть подходящее пространство в квартире.",
            AdoptionApplicationStatus.PENDING_REVIEW,
        ),
        (
            "user_demo2@example.com",
            "Боня",
            "Подали заявку на Боню, но пока переезжаем — не сможем взять в ближайший месяц.",
            AdoptionApplicationStatus.REJECTED,
        ),
        (
            "volunteer1@example.com",
            "Ричи",
            "Могу предложить короткую передержку и помощь на выходных.",
            AdoptionApplicationStatus.PENDING_REVIEW,
        ),
        (
            "volunteer2@example.com",
            "Грей",
            "Рассматриваем семейное пристройство, есть опыт с собаками.",
            AdoptionApplicationStatus.PENDING_REVIEW,
        ),
    ]

    days_ago = [2, 5, 1, 3, 1]
    for idx, (user_email, aname, message, status) in enumerate(specs):
        au = db.query(User).filter(User.email == user_email).first()
        if au is None:
            continue
        animal = animals.get(aname)
        if animal is None:
            continue
        exists = (
            db.query(AnimalAdoptionApplication.id)
            .filter(
                AnimalAdoptionApplication.user_id == au.id,
                AnimalAdoptionApplication.animal_id == animal.id,
            )
            .first()
        )
        if exists:
            continue
        created = datetime.utcnow() - timedelta(days=days_ago[idx % len(days_ago)])
        db.add(
            AnimalAdoptionApplication(
                user_id=au.id,
                animal_id=animal.id,
                status=status.value,
                message=message,
                created_at=created,
                updated_at=created,
            )
        )


def ensure_demo_organization_public_pages(db: Session, org1: Organization, org2: Organization) -> None:
    demo_desc = (
        "Мы спасаем крупных собак после ДТП и жестокого обращения: лечение, реабилитация, социализация "
        "и поиск дома. Сегодня под опекой более 150 животных."
    )
    placeholder = "Фонд помощи животным."
    if (org1.description or "").strip() in (placeholder, ""):
        org1.description = demo_desc
    org1.tagline = org1.tagline or "Помощь собакам крупного размера и собакам-инвалидам"
    if org1.city and org1.city.lower() == "москва":
        org1.city = "Екатеринбург"
    if (org1.city or "").strip().lower() == "екатеринбург":
        rl = (org1.region or "").strip().lower()
        if not org1.region or rl == "екатеринбург" or "свердловск" in rl:
            org1.region = "Свердловская область"
    org1.phone = org1.phone or "+7 (343) 000-00-01"
    org1.email = org1.email or "info@verni-drug.example.org"
    if not getattr(org1, "social_links_json", None):
        org1.social_links_json = json.dumps(
            [
                {"label": "Telegram", "url": "https://t.me/verni_drug_demo"},
                {"label": "ВКонтакте", "url": "https://vk.com/verni_drug_demo"},
                {"label": "Instagram", "url": "https://instagram.com/verni_drug_demo"},
            ],
            ensure_ascii=False,
        )
    org1.admission_rules = org1.admission_rules or (
        "Приём животных по предварительной записи после короткой анкеты. Работаем по согласованию с городскими службами."
    )
    org1.adoption_howto = org1.adoption_howto or (
        "Оставьте заявку на сайте или свяжитесь с куратором — подберём питомца и договоримся о знакомстве "
        "и условиях передачи."
    )
    org1.founded_year = org1.founded_year or 2015
    org1.about_html = org1.about_html or (
        "Фонд основан командой кинологов и ведёт прозрачную отчётность. Принимаем поддержку наличными "
        "и безналично, партнёрству рады всегда."
    )
    org1.gallery_json = org1.gallery_json or "[]"
    org1.inn = org1.inn or "6678099999"
    org1.ogrn = org1.ogrn or "1186678009999"
    org1.bank_account = org1.bank_account or "40702810000000000001"
    org1.has_chat_contact = True

    if not db.query(OrganizationReport).filter(OrganizationReport.organization_id == org1.id).first():
        db.add_all(
            [
                OrganizationReport(
                    organization_id=org1.id,
                    title="Отчёт за I квартал 2026",
                    summary="Расходы на корм, лечение и стерилизацию подопечных.",
                    body=None,
                    detail_url=None,
                    published_at=datetime(2026, 4, 1, 12, 0, 0),
                    is_published=True,
                ),
                OrganizationReport(
                    organization_id=org1.id,
                    title="Итоги зимней акции помощи",
                    summary="Поддержали передержки и закупили лекарственные средства.",
                    published_at=datetime(2026, 3, 18, 9, 0, 0),
                    is_published=True,
                ),
            ]
        )

    if (
        db.query(OrganizationHomeStory.id)
        .filter(OrganizationHomeStory.organization_id == org1.id)
        .first()
        is None
    ):
        db.add_all(
            [
                OrganizationHomeStory(
                    organization_id=org1.id,
                    animal_name="Майк",
                    story="Живёт в загородном доме с детьми: любит длинные прогулки и спокойные вечера у камина.",
                    photo_path=None,
                    adopted_at=date(2025, 11, 20),
                    sort_order=0,
                ),
                OrganizationHomeStory(
                    organization_id=org1.id,
                    animal_name="Лаки",
                    story="Стала первой собакой в семье, подружилась с домашним котом и осваивает городские парки.",
                    photo_path=None,
                    adopted_at=date(2026, 1, 8),
                    sort_order=1,
                ),
            ]
        )

    org2.tagline = org2.tagline or "Уютный приют для кошек и котят до постоянного дома"
    org2.has_chat_contact = False


def seed_demo_data_if_empty(db: Session) -> None:
    pw_demo = hash_password(_DEMO_LOGIN_PASSWORD_PLAIN)
    orgs = db.query(Organization).order_by(Organization.id.asc()).all()
    if len(orgs) < 2:
        org1 = Organization(
            name="Благотворительный фонд «Верный друг»",
            city="Екатеринбург",
            address="Екатеринбург, ул. Добрых дел, 10",
            specialization="both",
            needs_json=json.dumps(
                ["urgent", "volunteers", "auto", "fundraising"], ensure_ascii=False
            ),
            wards_count=150,
            adopted_yearly_count=47,
            description="Фонд помощи животным.",
            latitude=56.8389,
            longitude=60.6057,
        )
        org2 = Organization(
            name="Приют «Теплые лапы»",
            city="Санкт-Петербург",
            address="Санкт-Петербург, пр. Заботы, 5",
            specialization="cat",
            needs_json=json.dumps(["foster", "items", "fundraising", "volunteers"], ensure_ascii=False),
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

    org_user_1 = db.query(User).filter(User.email == "org1@example.com").first()
    if org_user_1 is None:
        org_user_1 = User(
            email="org1@example.com",
            phone="+79990000003",
            password_hash=pw_demo,
            full_name="Благотворительный фонд «Верный друг»",
            role=UserRole.ORGANIZATION,
            is_email_verified=True,
        )
        db.add(org_user_1)
        db.flush()
    org_user_2 = db.query(User).filter(User.email == "org2@example.com").first()
    if org_user_2 is None:
        org_user_2 = User(
            email="org2@example.com",
            phone="+79990000004",
            password_hash=pw_demo,
            full_name="Приют «Теплые лапы»",
            role=UserRole.ORGANIZATION,
            is_email_verified=True,
        )
        db.add(org_user_2)
        db.flush()
    if org1.owner_user_id is None:
        org1.owner_user_id = org_user_1.id
    if org2.owner_user_id is None:
        org2.owner_user_id = org_user_2.id

    if not db.query(VolunteerProfile.id).first():
        v1 = User(
            email="volunteer1@example.com",
            phone="+79990000001",
            password_hash=pw_demo,
            full_name="Анна Смирнова",
            role=UserRole.VOLUNTEER,
            is_email_verified=True,
        )
        v2 = User(
            email="volunteer2@example.com",
            phone="+79990000002",
            password_hash=pw_demo,
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

    volunteer_user = db.query(User).filter(User.role == UserRole.VOLUNTEER).order_by(User.id.asc()).first()
    organization_user = db.query(User).filter(User.role == UserRole.ORGANIZATION).order_by(User.id.asc()).first()
    if volunteer_user and organization_user:
        ensure_demo_knowledge_articles(db, volunteer_user.id, organization_user.id)
    ensure_demo_events(db, org1, org2)
    ensure_demo_urgent_requests(db, org1, org2)
    ensure_demo_organization_public_pages(db, org1, org2)

    enrich_demo_volunteers(db)

    ensure_demo_plain_users_and_adoption_applications(db)
    ensure_demo_volunteer_help_responses_lk_mock(db, org1)
    sync_demo_adoption_applications_for_profile_mock(db)
    sync_demo_accounts_password(db)

    db.commit()


def enrich_demo_volunteers(db: Session) -> None:
    ensure_volunteer_competency_items(db)
    demo_v1_weekly = [
        {"weekday": "monday", "ranges": [{"start": "16:00", "end": "21:00"}]},
        {"weekday": "tuesday", "ranges": [{"start": "10:00", "end": "14:00"}]},
        {"weekday": "wednesday", "ranges": [{"start": "12:00", "end": "15:00"}]},
        {"weekday": "thursday", "ranges": [{"start": "08:00", "end": "21:00"}]},
        {"weekday": "friday", "ranges": [{"start": "09:00", "end": "20:00"}]},
        {"weekday": "saturday", "ranges": [{"start": "09:00", "end": "20:00"}]},
        {"weekday": "sunday", "ranges": [{"start": "09:00", "end": "20:00"}]},
    ]
    v1 = db.query(User).filter(User.email == "volunteer1@example.com").first()
    if v1 and v1.volunteer_profile:
        p = v1.volunteer_profile
        _set_volunteer_competency_slugs(
            db,
            p.id,
            (
                "walk",
                "photo_video",
                "foster",
                "texts_social",
                "manual",
                "auto",
                "medical",
                "rescue",
            ),
        )
        p.animal_types_json = json.dumps(["dog", "cat"], ensure_ascii=False)
        if p.experience_level is None:
            p.experience_level = "experienced"
        p.about_me = (
            "Ветеринарный техник, 3 года стажа в приюте. Могу ставить капельницы, делать перевязки "
            "и работать с агрессивными животными. Дома живут две свои собаки."
        )
        p.completed_tasks_count = 24
        if p.latitude is None:
            p.latitude = 56.8389
        if p.longitude is None:
            p.longitude = 60.6057
        p.location_city = "Екатеринбург"
        p.location_district = "Кировский район"
        p.travel_radius_km = 30
        p.help_format = "recurring"
        p.has_veterinary_education = False
        p.accepts_night_urgency = False
        p.travel_area_mode = "region"
        p.weekly_availability_json = json.dumps(demo_v1_weekly, ensure_ascii=False)
        p.is_available = True
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
        if not p2.completed_tasks_count:
            p2.completed_tasks_count = 15
        if p2.latitude is None:
            p2.latitude = 59.9343
        if p2.longitude is None:
            p2.longitude = 30.3351


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
