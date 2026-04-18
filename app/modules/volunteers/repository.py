from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.profile import VolunteerProfile
from app.models.user import User, UserRole
from app.modules.volunteers.schemas import VolunteerFilterParams


class VolunteerRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_catalogs(self) -> list[str]:
        return [
            row[0]
            for row in self.db.query(VolunteerProfile.location_city)
            .distinct()
            .order_by(VolunteerProfile.location_city.asc())
            .all()
            if row[0]
        ]

    def list_volunteers(self, filters: VolunteerFilterParams) -> tuple[int, list[tuple[User, VolunteerProfile]]]:
        q = (
            self.db.query(User, VolunteerProfile)
            .join(VolunteerProfile, VolunteerProfile.user_id == User.id)
            .filter(User.role == UserRole.VOLUNTEER)
        )

        if filters.q:
            like = f"%{filters.q.lower()}%"
            q = q.filter(
                or_(
                    func.lower(User.full_name).like(like),
                    func.lower(VolunteerProfile.skills).like(like),
                    func.lower(VolunteerProfile.experience).like(like),
                )
            )
        if filters.city:
            q = q.filter(func.lower(VolunteerProfile.location_city) == filters.city.lower())
        if filters.animal_category:
            like_cat = f"%{filters.animal_category.lower()}%"
            q = q.filter(func.lower(VolunteerProfile.animal_categories).like(like_cat))
        if filters.has_transport is True:
            q = q.filter(func.lower(VolunteerProfile.skills).like("%транспорт%"))
        elif filters.has_transport is False:
            q = q.filter(~func.lower(VolunteerProfile.skills).like("%транспорт%"))

        total = q.count()

        if filters.sort_by == "city":
            q = q.order_by(VolunteerProfile.location_city.asc().nulls_last())
        else:
            q = q.order_by(User.full_name.asc().nulls_last(), User.id.asc())

        items = q.offset(filters.offset).limit(filters.limit).all()
        return total, items
