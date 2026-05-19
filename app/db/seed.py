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
from app.models.org_chat import OrgChatDialog, OrgChatMessage
from app.models.organization_home_story import OrganizationHomeStory
from app.models.organization_report import OrganizationReport
from app.models.profile import UserProfile, VolunteerProfile
from app.models.volunteer_competency import VolunteerCompetencyAssignment, VolunteerCompetencyItem
from app.models.user import User, UserRole
from app.modules.organizations.public_catalog import DEFAULT_HELP_SECTIONS
from app.modules.volunteers.constants import COMPETENCY_OPTIONS

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SEED_ANIMAL_IMAGES_DIR = _REPO_ROOT / "seed_images" / "animals"
_SEED_URGENT_IMAGES_DIR = _REPO_ROOT / "seed_images" / "urgent"
_SEED_ORG1_GALLERY_DIR = _REPO_ROOT / "seed_images" / "org1_gallery"

_DEMO_HOME_STORY_PHOTOS: dict[str, str] = {
    "Майк": "grey.png",
    "Лаки": "richi.png",
    "Боня": "bonya.png",
}

_DEMO_ARTICLE_COVERS: tuple[tuple[str, str, str], ...] = (
    ("Как кормить кошку в период адаптации", "article_care_org.png", "marusya.png"),
    ("Первая помощь при небольшом порезе лапы", "article_first_aid_vol.png", "musya.png"),
    ("Юридические вопросы при пристройстве", "article_legal_org.png", "grey.png"),
    ("Как правильно кормить кошку в период адаптации", "article_care_vol.png", "bonya.png"),
)

_HELP_SECTION_IMAGE_SOURCES: dict[str, str] = {
    "financial": "musya.png",
    "volunteering": "richi.png",
    "foster": "marusya.png",
    "items": "bonya.png",
    "auto": "grey.png",
}
_ORG1_GALLERY_SEED_FILES: tuple[str, ...] = (
    "org1_gallery_1.png",
    "org1_gallery_2.png",
    "org1_gallery_3.png",
)

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


def _materialize_org1_gallery_images() -> list[str]:
    dest = Path(settings.media_dir) / "demo_org1_gallery"
    dest.mkdir(parents=True, exist_ok=True)
    rel_paths: list[str] = []
    for name in _ORG1_GALLERY_SEED_FILES:
        src = _SEED_ORG1_GALLERY_DIR / name
        if not src.is_file():
            continue
        shutil.copy2(src, dest / name)
        rel_paths.append(f"demo_org1_gallery/{name}")
    return rel_paths


def _copy_seed_animal_asset(dest_subdir: str, dest_name: str, source_name: str) -> str | None:
    src = _SEED_ANIMAL_IMAGES_DIR / source_name
    if not src.is_file():
        return None
    dest = Path(settings.media_dir) / dest_subdir
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest / dest_name)
    return f"{dest_subdir}/{dest_name}"


def _materialize_demo_help_section_images() -> bool:
    if not _SEED_ANIMAL_IMAGES_DIR.is_dir():
        return False
    ok = True
    for kind, source in _HELP_SECTION_IMAGE_SOURCES.items():
        if _copy_seed_animal_asset("demo_help_sections", f"{kind}.png", source) is None:
            ok = False
    return ok


def _demo_help_sections_json(photos_ready: bool) -> str:
    if not photos_ready:
        return "[]"
    rows: list[dict[str, str]] = []
    for section in DEFAULT_HELP_SECTIONS:
        kind = section["kind"]
        rows.append(
            {
                "kind": kind,
                "title": section["title"],
                "description": section["description"],
                "primary_action": section["primary_action"],
                "image_path": f"demo_help_sections/{kind}.png",
            }
        )
    return json.dumps(rows, ensure_ascii=False)


def _sync_demo_home_story_photos(db: Session, organization_id: int, photos_ready: bool) -> None:
    if not photos_ready:
        return
    for animal_name, source in _DEMO_HOME_STORY_PHOTOS.items():
        rel = _copy_seed_animal_asset("demo_home_stories", f"{animal_name}.png", source)
        if rel is None:
            continue
        story = (
            db.query(OrganizationHomeStory)
            .filter(
                OrganizationHomeStory.organization_id == organization_id,
                OrganizationHomeStory.animal_name == animal_name,
            )
            .first()
        )
        if story is not None:
            story.photo_path = rel


def _sync_demo_article_covers(db: Session, photos_ready: bool) -> None:
    if not photos_ready:
        return
    for title, dest_name, source in _DEMO_ARTICLE_COVERS:
        rel = _copy_seed_animal_asset("demo_articles", dest_name, source)
        if rel is None:
            continue
        articles = db.query(KnowledgeArticle).filter(KnowledgeArticle.title == title).all()
        for article in articles:
            article.cover_path = rel


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
    db.flush()


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
    slug_to_id = _volunteer_competency_slug_to_id(db)
    seen: set[str] = set()
    desired_ids: list[int] = []
    for s in slugs:
        if s in seen:
            continue
        seen.add(s)
        cid = slug_to_id.get(s)
        if cid is not None:
            desired_ids.append(cid)
    desired_set = set(desired_ids)

    existing = (
        db.query(VolunteerCompetencyAssignment)
        .filter(VolunteerCompetencyAssignment.volunteer_profile_id == profile_id)
        .all()
    )
    existing_by_cid = {a.competency_item_id: a for a in existing}
    for cid, assignment in existing_by_cid.items():
        if cid not in desired_set:
            db.delete(assignment)
    for cid in desired_ids:
        if cid not in existing_by_cid:
            db.add(
                VolunteerCompetencyAssignment(
                    volunteer_profile_id=profile_id,
                    competency_item_id=cid,
                )
            )


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

    _sync_demo_article_covers(db, _SEED_ANIMAL_IMAGES_DIR.is_dir())


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
    "Кошке Мусе требуется поездка в ветеринарную клинику на операцию. "
    "Самостоятельно доставить животное нет возможности, поэтому ищем волонтера с машиной. "
    "Муся спокойная, находится в переноске.\n\n"
    "Маршрут:\n"
    "• Откуда: Передержка, ул. Ленина, 10\n"
    '• Куда: Ветклиника «Айболит», ул. Мира, 25\n\n'
    "Что нужно сделать: забрать животное с передержки -> аккуратно перевезти в клинику -> передать "
    "сотрудникам.\n\n"
    "Дополнительно: переноска предоставляется."
)


def _migrate_lk_demo_help_request_titles(
    db: Session,
    volunteer_user_id: int,
    organization_id: int,
    demo_title: str,
    today_17: datetime,
    today_17b: datetime,
    may7_12: datetime,
    musya_id: int | None,
) -> None:
    rows = (
        db.query(VolunteerHelpResponse)
        .options(joinedload(VolunteerHelpResponse.help_request))
        .filter(VolunteerHelpResponse.volunteer_user_id == volunteer_user_id)
        .all()
    )
    for row in rows:
        hr = row.help_request
        if hr is None or hr.organization_id != organization_id:
            continue
        if hr.help_type != "auto":
            continue
        if musya_id is not None:
            if hr.animal_id != musya_id:
                continue
        elif hr.title != demo_title:
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


def _sync_demo_transport_lk_requests_copy(
    db: Session,
    org_id: int,
    demo_title: str,
    animal_id: int | None,
) -> None:
    rows = (
        db.query(HelpRequest)
        .filter(
            HelpRequest.organization_id == org_id,
            HelpRequest.title == demo_title,
            HelpRequest.help_type == "auto",
        )
        .all()
    )
    targets = rows if animal_id is None else [hr for hr in rows if hr.animal_id == animal_id]
    for hr in targets:
        hr.description = _DEMO_LK_TRANSPORT_DESCRIPTION
        hr.volunteer_requirements = (
            "Нужен волонтёр с автомобилем и опытом перевозки животных."
        )
        if hr.is_urgent:
            hr.deadline_note = "Сегодня, 17:00"
        elif (hr.deadline_note or "").strip() == "Сегодня, 17:00":
            hr.deadline_note = None


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
            "deadline_note": "Сегодня, 17:00",
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
        db, v.id, org1.id, demo_title, today_17, today_17b, may7_12, musya.id if musya else None
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
            "volunteer_requirements": "Нужен волонтёр с автомобилем и опытом перевозки животных.",
            "volunteer_competencies_json": json.dumps(["auto"], ensure_ascii=False),
            "target_amount": None,
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
                "Мусю доставили в ветклинику «Айболит» на ул. Мира, врач принял животное, состояние стабильное."
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

    musya_id = musya.id if musya else None
    _sync_demo_transport_lk_requests_copy(db, org1.id, demo_title, musya_id)


def _demo_adoption_form_kwargs(
    *,
    applicant_name: str,
    applicant_email: str,
    applicant_phone: str,
    applicant_age: int = 28,
    housing_type: str = "apartment",
    housing_ownership: str = "own",
    residents_consent: bool = True,
    has_children: bool = False,
    has_allergy: bool = False,
    had_pets_before: bool = False,
    has_pets_now: bool = False,
    pet_experience: str = "",
    why_now: str = "Хочу подарить дом питомцу.",
    who_looking_for: str = "Спокойный темперамент, средний возраст.",
    ready_for_vet_costs: bool = True,
    feeding_plan: str = "Сухой корм премиум-класса",
    ready_for_vaccination: bool = True,
    time_to_devote: str = "2–3 часа в день",
    vacation_care: str = "Родственники",
    return_plan: str = "Верну в приют и обсужу с куратором.",
    ready_to_sign_contract: bool = True,
    ready_to_show_conditions: bool = True,
    ready_to_keep_in_touch: bool = True,
) -> dict:
    return {
        "applicant_name": applicant_name,
        "applicant_age": applicant_age,
        "applicant_phone": applicant_phone,
        "applicant_email": applicant_email,
        "housing_type": housing_type,
        "housing_ownership": housing_ownership,
        "residents_consent": residents_consent,
        "has_children": has_children,
        "has_allergy": has_allergy,
        "had_pets_before": had_pets_before,
        "has_pets_now": has_pets_now,
        "pet_experience": pet_experience,
        "why_now": why_now,
        "who_looking_for": who_looking_for,
        "ready_for_vet_costs": ready_for_vet_costs,
        "feeding_plan": feeding_plan,
        "ready_for_vaccination": ready_for_vaccination,
        "time_to_devote": time_to_devote,
        "vacation_care": vacation_care,
        "return_plan": return_plan,
        "ready_to_sign_contract": ready_to_sign_contract,
        "ready_to_show_conditions": ready_to_show_conditions,
        "ready_to_keep_in_touch": ready_to_keep_in_touch,
    }


def sync_demo_adoption_applications_for_profile_mock(db: Session) -> None:
    u = db.query(User).filter(User.email == "user_demo@example.com").first()
    if u is None:
        return

    targets: list[tuple[str, dict]] = [
        (
            "Муся",
            _demo_adoption_form_kwargs(
                applicant_name=u.full_name or "Демо пользователь",
                applicant_email=u.email,
                applicant_phone=u.phone or "+79001234567",
                why_now="Готова обсудить условия и приехать на знакомство с Мусей.",
            ),
        ),
        (
            "Маруся",
            _demo_adoption_form_kwargs(
                applicant_name=u.full_name or "Демо пользователь",
                applicant_email=u.email,
                applicant_phone=u.phone or "+79001234567",
                who_looking_for="Маруся понравилась по описанию, есть подходящее пространство в квартире.",
            ),
        ),
    ]

    for aname, form_kwargs in targets:
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
                    message=None,
                    created_at=ts,
                    updated_at=ts,
                    **form_kwargs,
                )
            )
        else:
            row.status = AdoptionApplicationStatus.PENDING_REVIEW.value
            row.message = None
            for key, value in form_kwargs.items():
                setattr(row, key, value)
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

    specs: list[tuple[str, str, AdoptionApplicationStatus, dict, str | None]] = [
        (
            "user_demo@example.com",
            "Муся",
            AdoptionApplicationStatus.PENDING_REVIEW,
            _demo_adoption_form_kwargs(
                applicant_name="Демо пользователь",
                applicant_email="user_demo@example.com",
                applicant_phone="+79001234567",
                why_now="Здравствуйте! Готова обсудить условия и приехать на знакомство.",
            ),
            None,
        ),
        (
            "user_demo@example.com",
            "Маруся",
            AdoptionApplicationStatus.PENDING_REVIEW,
            _demo_adoption_form_kwargs(
                applicant_name="Демо пользователь",
                applicant_email="user_demo@example.com",
                applicant_phone="+79001234567",
                who_looking_for="Маруся понравилась по описанию, есть подходящее пространство в квартире.",
            ),
            None,
        ),
        (
            "user_demo2@example.com",
            "Боня",
            AdoptionApplicationStatus.REJECTED,
            _demo_adoption_form_kwargs(
                applicant_name="Анна Демо",
                applicant_email="user_demo2@example.com",
                applicant_phone="+79001112233",
                why_now="Подали заявку на Боню, но пока переезжаем.",
            ),
            "Подали заявку на Боню, но пока переезжаем — не сможем взять в ближайший месяц.",
        ),
        (
            "volunteer1@example.com",
            "Ричи",
            AdoptionApplicationStatus.PENDING_REVIEW,
            _demo_adoption_form_kwargs(
                applicant_name="Волонтёр 1",
                applicant_email="volunteer1@example.com",
                applicant_phone="+79002223344",
                why_now="Могу предложить короткую передержку и помощь на выходных.",
            ),
            None,
        ),
        (
            "volunteer2@example.com",
            "Грей",
            AdoptionApplicationStatus.PENDING_REVIEW,
            _demo_adoption_form_kwargs(
                applicant_name="Волонтёр 2",
                applicant_email="volunteer2@example.com",
                applicant_phone="+79003334455",
                why_now="Рассматриваем семейное пристройство, есть опыт с собаками.",
            ),
            None,
        ),
    ]

    days_ago = [2, 5, 1, 3, 1]
    for idx, (user_email, aname, status, form_kwargs, rejection_message) in enumerate(specs):
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
                message=rejection_message,
                created_at=created,
                updated_at=created,
                **form_kwargs,
            )
        )


def ensure_demo_organization_public_pages(db: Session, org1: Organization, org2: Organization) -> None:
    org1_gallery_paths = _materialize_org1_gallery_images()
    help_photos_ready = _materialize_demo_help_section_images()
    help_sections_json = _demo_help_sections_json(help_photos_ready)
    org1.name = "Благотворительный фонд «Верный друг»"
    org1.tagline = "Помощь собакам крупного размера и собакам-инвалидам"
    org1.description = (
        "Мы спасаем крупных собак, пострадавших от жестокого обращения или ДТП. "
        "Лечим, социализируем и находим им новые семьи. Под нашей опекой сейчас находится 150 хвостиков."
    )
    org1.city = "Екатеринбург"
    org1.region = "Свердловская область"
    org1.address = "Екатеринбург, ул. Добрых дел, 10"
    org1.phone = "+7 (927) 412-58-90"
    org1.email = "info@dobryelapy.ru"
    org1.social_links_json = json.dumps(
        [
            {"platform": "vk", "url": "https://vk.com/verni_drug_demo"},
            {"platform": "telegram", "url": "https://t.me/verni_drug_demo"},
            {"platform": "whatsapp", "url": "https://wa.me/79274125890"},
        ],
        ensure_ascii=False,
    )
    org1.admission_rules = "Правила приема животных"
    org1.adoption_howto = "Как приютить питомца"
    org1.founded_year = 2015
    org1.about_html = (
        "Приют «Лапа Надежды» помогает бездомным животным, оказавшимся на улице, после жестокого обращения "
        "или потери дома. Мы занимаемся лечением, стерилизацией, вакцинацией, социализацией и поиском "
        "ответственных хозяев. За несколько лет работы через нас прошли сотни животных. Сейчас в приюте "
        "живут кошки и собаки разного возраста и характера.\n\n"
        "Наши основные задачи:\n"
        "- Лечение и реабилитация тяжелобольных животных.\n"
        "- Поиск новых семей и кураторов.\n"
        "- Помощь в передержке и адаптации.\n"
        "- Просветительская работа об ответственном обращении с питомцами."
    )
    org1.gallery_json = json.dumps(org1_gallery_paths, ensure_ascii=False)
    org1.inn = "1658123471"
    org1.ogrn = "1181960045123"
    org1.bank_account = "40702810962000018452"
    org1.has_chat_contact = True
    if help_sections_json != "[]":
        org1.help_sections_json = help_sections_json

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
                    photo_path=_copy_seed_animal_asset(
                        "demo_home_stories", "Майк.png", _DEMO_HOME_STORY_PHOTOS["Майк"]
                    ),
                    adopted_at=date(2025, 11, 20),
                ),
                OrganizationHomeStory(
                    organization_id=org1.id,
                    animal_name="Лаки",
                    story="Стала первой собакой в семье, подружилась с домашним котом и осваивает городские парки.",
                    photo_path=_copy_seed_animal_asset(
                        "demo_home_stories", "Лаки.png", _DEMO_HOME_STORY_PHOTOS["Лаки"]
                    ),
                    adopted_at=date(2026, 1, 8),
                ),
            ]
        )
    _sync_demo_home_story_photos(db, org1.id, help_photos_ready)

    org2.tagline = org2.tagline or "Уютный приют для кошек и котят до постоянного дома"
    org2.description = org2.description or "Приют для кошек и котят. Помогаем с лечением и поиском дома."
    org2.region = "Ленинградская область"
    org2.phone = org2.phone or "+7 (812) 000-00-02"
    org2.email = org2.email or "help@teplye-lapy.example.org"
    if not getattr(org2, "social_links_json", None):
        org2.social_links_json = json.dumps(
            [
                {"platform": "telegram", "url": "https://t.me/teplye_lapy_demo"},
                {"platform": "vk", "url": "https://vk.com/teplye_lapy_demo"},
            ],
            ensure_ascii=False,
        )
    org2.admission_rules = org2.admission_rules or "Принимаем животных после первичного осмотра и диагностики."
    org2.adoption_howto = org2.adoption_howto or "Заполните анкету, далее согласуем знакомство с питомцем."
    org2.founded_year = org2.founded_year or 2018
    org2.about_html = org2.about_html or "Мы специализируемся на помощи кошкам и котятам в сложных ситуациях."
    org2.gallery_json = org2.gallery_json or "[]"
    org2.inn = org2.inn or "7812456700"
    org2.ogrn = org2.ogrn or "1197800001234"
    org2.bank_account = org2.bank_account or "40702810000000000002"
    org2.has_chat_contact = True
    if help_sections_json != "[]":
        org2.help_sections_json = help_sections_json
    if not db.query(OrganizationReport).filter(OrganizationReport.organization_id == org2.id).first():
        db.add_all(
            [
                OrganizationReport(
                    organization_id=org2.id,
                    title="Отчёт за апрель 2026",
                    summary="Содержание, лечение и пристройство кошек.",
                    body="Краткий отчёт о расходах и результатах работы приюта за апрель.",
                    detail_url=None,
                    published_at=datetime(2026, 4, 30, 18, 0, 0),
                    is_published=True,
                ),
            ]
        )
    if (
        db.query(OrganizationHomeStory.id)
        .filter(OrganizationHomeStory.organization_id == org2.id)
        .first()
        is None
    ):
        db.add_all(
            [
                OrganizationHomeStory(
                    organization_id=org2.id,
                    animal_name="Боня",
                    story="Боня уехала в новую семью и уже освоилась в квартире.",
                    photo_path=_copy_seed_animal_asset(
                        "demo_home_stories", "Боня.png", _DEMO_HOME_STORY_PHOTOS["Боня"]
                    ),
                    adopted_at=date(2026, 2, 12),
                )
            ]
        )
    _sync_demo_home_story_photos(db, org2.id, help_photos_ready)


def ensure_demo_org_comms(db: Session, org: Organization) -> None:
    org_user = db.query(User).filter(User.id == org.owner_user_id).first() if org.owner_user_id else None
    if org_user is None:
        return

    volunteer = db.query(User).filter(User.email == "volunteer1@example.com").first()
    adopter = db.query(User).filter(User.email == "user_demo@example.com").first()
    if volunteer is None or adopter is None:
        return

    animal = (
        db.query(Animal)
        .filter(Animal.organization_id == org.id)
        .order_by(Animal.created_at.desc(), Animal.id.desc())
        .first()
    )
    animal_name = animal.name if animal else "подопечного"
    ctx = f"Анкета на {animal_name}"
    dialog = (
        db.query(OrgChatDialog)
        .filter(
            OrgChatDialog.organization_id == org.id,
            OrgChatDialog.participant_user_id == adopter.id,
            OrgChatDialog.context_title == ctx,
        )
        .first()
    )
    if dialog is None:
        dialog = OrgChatDialog(
            organization_id=org.id,
            participant_user_id=adopter.id,
            participant_name=adopter.full_name or "Пользователь",
            participant_avatar_path=None,
            context_type="adoption_application",
            context_entity_id=animal.id if animal else None,
            context_title=ctx,
            last_message_preview=None,
            last_message_at=None,
            unread_count_org=0,
            unread_count_volunteer=0,
            unread_count_user=0,
        )
        db.add(dialog)
        db.flush()
    if not db.query(OrgChatMessage.id).filter(OrgChatMessage.dialog_id == dialog.id).first():
        m1 = OrgChatMessage(
            dialog_id=dialog.id,
            sender_user_id=org_user.id,
            sender_role=UserRole.ORGANIZATION.value,
            body=(
                f"Добрый день! Получили анкету на {animal_name}. "
                "Можем согласовать знакомство в субботу после 14:00."
            ),
            read_by_org_at=None,
        )
        m2 = OrgChatMessage(
            dialog_id=dialog.id,
            sender_user_id=adopter.id,
            sender_role=UserRole.USER.value,
            body="Здравствуйте! Спасибо, в субботу после 14:00 подойду.",
            read_by_org_at=None,
        )
        db.add_all([m1, m2])
        db.flush()
        dialog.last_message_preview = m2.body
        dialog.last_message_at = m2.created_at
        dialog.unread_count_org = 1
        dialog.unread_count_user = 0

    help_req = (
        db.query(HelpRequest)
        .filter(HelpRequest.organization_id == org.id)
        .order_by(HelpRequest.created_at.desc(), HelpRequest.id.desc())
        .first()
    )
    ctx2 = f"Отклик волонтёра: {help_req.title if help_req else 'Задача'}"
    dialog2 = (
        db.query(OrgChatDialog)
        .filter(
            OrgChatDialog.organization_id == org.id,
            OrgChatDialog.participant_user_id == volunteer.id,
            OrgChatDialog.context_title == ctx2,
        )
        .first()
    )
    if dialog2 is None:
        dialog2 = OrgChatDialog(
            organization_id=org.id,
            participant_user_id=volunteer.id,
            participant_name=volunteer.full_name or "Волонтёр",
            participant_avatar_path=None,
            context_type="volunteer_response",
            context_entity_id=help_req.id if help_req else None,
            context_title=ctx2,
            unread_count_org=0,
            unread_count_volunteer=0,
            unread_count_user=0,
        )
        db.add(dialog2)
        db.flush()
    if not db.query(OrgChatMessage.id).filter(OrgChatMessage.dialog_id == dialog2.id).first():
        n1 = OrgChatMessage(
            dialog_id=dialog2.id,
            sender_user_id=org_user.id,
            sender_role=UserRole.ORGANIZATION.value,
            body="Здравствуйте! Есть задача на перевозку — напишите, если готовы помочь.",
            read_by_org_at=None,
        )
        n2 = OrgChatMessage(
            dialog_id=dialog2.id,
            sender_user_id=volunteer.id,
            sender_role=UserRole.VOLUNTEER.value,
            body="Готов взять задачу на перевозку, автомобиль и переноска есть.",
            read_by_org_at=None,
        )
        db.add_all([n1, n2])
        db.flush()
        dialog2.last_message_preview = n2.body
        dialog2.last_message_at = n2.created_at
        dialog2.unread_count_org = 1
        dialog2.unread_count_volunteer = 0


def ensure_demo_org2_incoming_volunteer_response(db: Session, org2: Organization) -> None:
    volunteer = db.query(User).filter(User.email == "volunteer2@example.com").first()
    if volunteer is None:
        return
    req = (
        db.query(HelpRequest)
        .filter(HelpRequest.organization_id == org2.id, HelpRequest.status == "open")
        .order_by(HelpRequest.created_at.desc(), HelpRequest.id.desc())
        .first()
    )
    if req is None:
        return
    exists = (
        db.query(VolunteerHelpResponse.id)
        .filter(
            VolunteerHelpResponse.volunteer_user_id == volunteer.id,
            VolunteerHelpResponse.help_request_id == req.id,
        )
        .first()
    )
    if exists:
        return
    now = datetime.utcnow()
    db.add(
        VolunteerHelpResponse(
            volunteer_user_id=volunteer.id,
            help_request_id=req.id,
            status=VolunteerHelpResponseStatus.PENDING.value,
            message="Готов помочь по задаче, есть опыт и свободное время вечером.",
            created_at=now,
            updated_at=now,
        )
    )


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
    ensure_demo_org2_incoming_volunteer_response(db, org2)
    sync_demo_adoption_applications_for_profile_mock(db)
    ensure_demo_org_comms(db, org1)
    ensure_demo_org_comms(db, org2)
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
        if not p2.help_format:
            p2.help_format = "one_time"


if __name__ == "__main__":
    from app.db.bootstrap import init_db
    from app.db.session import SessionLocal, engine

    init_db(engine)
    session = SessionLocal()
    try:
        seed_demo_data_if_empty(session)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    print("seed_demo_data_if_empty: OK")
