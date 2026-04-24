from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.animal import Animal, AnimalPhoto
from app.models.animal_catalog import AnimalCatalogAssignment, AnimalCatalogItem
from app.models.organization import Organization
from app.modules.animals.catalog_constants import FEATURE_ID_HEALTH_NOTES, FEATURE_ID_URGENT
from app.modules.animals.schemas import AnimalFilterParams


class AnimalRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, animal_id: int) -> Animal | None:
        return (
            self.db.query(Animal)
            .options(
                joinedload(Animal.photos),
                joinedload(Animal.organization),
                selectinload(Animal.help_requests),
                selectinload(Animal.catalog_assignments).selectinload(AnimalCatalogAssignment.catalog_item),
            )
            .filter(Animal.id == animal_id)
            .first()
        )

    def get_catalogs(self) -> tuple[list[str], list[str], list[str]]:
        statuses = [
            row[0]
            for row in self.db.query(Animal.status).distinct().order_by(Animal.status.asc()).all()
            if row[0]
        ]
        sexes = [
            row[0] for row in self.db.query(Animal.sex).distinct().order_by(Animal.sex.asc()).all() if row[0]
        ]
        cities = [
            row[0]
            for row in self.db.query(Animal.location_city)
            .distinct()
            .order_by(Animal.location_city.asc())
            .all()
            if row[0]
        ]
        return statuses, sexes, cities

    def list_organization_options(self) -> list[tuple[int, str]]:
        rows = self.db.query(Organization.id, Organization.name).order_by(Organization.name.asc()).all()
        return [(r[0], r[1]) for r in rows]

    def catalog_label_map(self, kind: str) -> dict[str, str]:
        rows = (
            self.db.query(AnimalCatalogItem)
            .filter(AnimalCatalogItem.kind == kind, AnimalCatalogItem.is_active.is_(True))
            .order_by(AnimalCatalogItem.sort_order.asc(), AnimalCatalogItem.slug.asc())
            .all()
        )
        return {r.slug: r.label for r in rows}

    def list_catalog_options(self, kind: str) -> list[tuple[str, str]]:
        rows = (
            self.db.query(AnimalCatalogItem)
            .filter(AnimalCatalogItem.kind == kind, AnimalCatalogItem.is_active.is_(True))
            .order_by(AnimalCatalogItem.sort_order.asc(), AnimalCatalogItem.slug.asc())
            .all()
        )
        return [(r.slug, r.label) for r in rows]

    def _catalog_assignment_exists(self, kind: str, slug_lc: str):
        return (
            self.db.query(AnimalCatalogAssignment.id)
            .join(AnimalCatalogItem, AnimalCatalogItem.id == AnimalCatalogAssignment.catalog_item_id)
            .filter(AnimalCatalogAssignment.animal_id == Animal.id)
            .filter(AnimalCatalogItem.kind == kind)
            .filter(func.lower(AnimalCatalogItem.slug) == slug_lc)
            .exists()
        )

    @staticmethod
    def _animal_has_health_notes_sql():
        return or_(
            func.trim(func.coalesce(Animal.health_features, "")) != "",
            func.trim(func.coalesce(Animal.treatment_required, "")) != "",
        )

    def add_photo(self, animal_id: int, file_path: str, is_primary: bool):
        if is_primary:
            self.db.query(AnimalPhoto).filter(AnimalPhoto.animal_id == animal_id).update(
                {AnimalPhoto.is_primary: False}
            )

        photo = AnimalPhoto(animal_id=animal_id, file_path=file_path, is_primary=is_primary)
        self.db.add(photo)
        self.db.commit()
        self.db.refresh(photo)
        return photo

    def list_animals(self, filters: AnimalFilterParams) -> tuple[int, list[Animal]]:
        query = self.db.query(Animal).options(
            joinedload(Animal.photos),
            joinedload(Animal.organization),
            selectinload(Animal.catalog_assignments).selectinload(AnimalCatalogAssignment.catalog_item),
        )

        if filters.q:
            like = f"%{filters.q.lower()}%"
            query = query.filter(
                or_(
                    func.lower(Animal.name).like(like),
                    func.lower(Animal.full_description).like(like),
                )
            )
        if filters.city:
            query = query.filter(func.lower(Animal.location_city) == filters.city.lower())
        if filters.status:
            query = query.filter(Animal.status == filters.status)
        if filters.sex:
            query = query.filter(Animal.sex == filters.sex)
        if filters.species:
            query = query.filter(Animal.species == filters.species)
        if filters.organization_id is not None:
            query = query.filter(Animal.organization_id == filters.organization_id)
        if filters.age_group == "baby":
            query = query.filter(Animal.age_months <= 11)
        elif filters.age_group == "adult":
            query = query.filter(Animal.age_months >= 12)

        for fid in filters.features:
            token = fid.strip()
            if not token:
                continue
            tl = token.lower()
            if tl == FEATURE_ID_URGENT:
                query = query.filter(Animal.is_urgent.is_(True))
            elif tl == FEATURE_ID_HEALTH_NOTES:
                query = query.filter(self._animal_has_health_notes_sql())
            elif "/" in token:
                kind, slug = token.split("/", 1)
                kl, sl = kind.strip().lower(), slug.strip().lower()
                if kl in ("health_care", "character"):
                    query = query.filter(self._catalog_assignment_exists(kl, sl))
            else:
                query = query.filter(
                    or_(self._catalog_assignment_exists("health_care", tl), self._catalog_assignment_exists("character", tl))
                )

        if filters.is_urgent is not None:
            query = query.filter(Animal.is_urgent == filters.is_urgent)
        if filters.min_age_months is not None:
            query = query.filter(Animal.age_months >= filters.min_age_months)
        if filters.max_age_months is not None:
            query = query.filter(Animal.age_months <= filters.max_age_months)

        total = query.count()

        if filters.sort_by == "age_months":
            query = query.order_by(asc(Animal.age_months))
        elif filters.sort_by == "-age_months":
            query = query.order_by(desc(Animal.age_months))
        elif filters.sort_by == "-created_at":
            query = query.order_by(desc(Animal.created_at))
        elif filters.sort_by == "name":
            query = query.order_by(asc(Animal.name))
        else:
            query = query.order_by(asc(Animal.created_at))

        items = query.offset(filters.offset).limit(filters.limit).all()
        return total, items
