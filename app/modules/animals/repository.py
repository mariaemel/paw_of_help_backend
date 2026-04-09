from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.animal import Animal, AnimalPhoto
from app.modules.animals.schemas import AnimalFilterParams


class AnimalRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, animal_id: int) -> Animal | None:
        return (
            self.db.query(Animal)
            .options(joinedload(Animal.photos))
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

    def add_photo(self, animal_id: int, file_path: str, is_primary: bool) -> AnimalPhoto:
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
        query = self.db.query(Animal).options(joinedload(Animal.photos))

        if filters.q:
            like = f"%{filters.q.lower()}%"
            query = query.filter(
                or_(func.lower(Animal.name).like(like), func.lower(Animal.short_story).like(like))
            )
        if filters.city:
            query = query.filter(func.lower(Animal.location_city) == filters.city.lower())
        if filters.status:
            query = query.filter(Animal.status == filters.status)
        if filters.sex:
            query = query.filter(Animal.sex == filters.sex)
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
        else:
            query = query.order_by(asc(Animal.created_at))

        items = query.offset(filters.offset).limit(filters.limit).all()
        return total, items
