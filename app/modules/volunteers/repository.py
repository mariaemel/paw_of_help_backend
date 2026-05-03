import math

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.knowledge import KnowledgeArticle
from app.models.profile import VolunteerProfile
from app.models.user import User, UserRole
from app.models.volunteer_competency import VolunteerCompetencyAssignment, VolunteerCompetencyItem
from app.modules.volunteers.schemas import VolunteerFilterParams


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p = math.pi / 180
    a = (
        0.5
        - math.cos((lat2 - lat1) * p) / 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    )
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _profile_has_competency_slug(slug: str):
    return exists(
        select(1)
        .select_from(VolunteerCompetencyAssignment)
        .join(
            VolunteerCompetencyItem,
            VolunteerCompetencyItem.id == VolunteerCompetencyAssignment.competency_item_id,
        ).where(
            VolunteerCompetencyAssignment.volunteer_profile_id == VolunteerProfile.id,
            VolunteerCompetencyItem.slug == slug,
        )
    )


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

    def list_competency_catalog(self) -> list[VolunteerCompetencyItem]:
        return (
            self.db.query(VolunteerCompetencyItem)
            .filter(VolunteerCompetencyItem.is_active.is_(True))
            .order_by(VolunteerCompetencyItem.sort_order.asc(), VolunteerCompetencyItem.slug.asc())
            .all()
        )

    def get_volunteer(self, user_id: int) -> tuple[User, VolunteerProfile] | None:
        row = (
            self.db.query(User, VolunteerProfile)
            .options(
                selectinload(User.volunteer_profile)
                .selectinload(VolunteerProfile.competency_assignments)
                .selectinload(VolunteerCompetencyAssignment.competency_item)
            )
            .join(VolunteerProfile, VolunteerProfile.user_id == User.id)
            .filter(User.id == user_id, User.role == UserRole.VOLUNTEER)
            .first()
        )
        return row

    def list_published_articles_by_volunteer(
        self, author_user_id: int, limit: int = 24
    ) -> list[KnowledgeArticle]:
        return (
            self.db.query(KnowledgeArticle)
            .filter(
                KnowledgeArticle.author_user_id == author_user_id,
                KnowledgeArticle.owner_role == "volunteer",
                KnowledgeArticle.is_published.is_(True),
                KnowledgeArticle.is_archived.is_(False),
            )
            .order_by(KnowledgeArticle.created_at.desc())
            .limit(limit)
            .all()
        )

    def list_volunteers(self, filters: VolunteerFilterParams) -> tuple[int, list[tuple[User, VolunteerProfile]]]:
        q = (
            self.db.query(User, VolunteerProfile)
            .join(VolunteerProfile, VolunteerProfile.user_id == User.id)
            .options(
                selectinload(User.volunteer_profile)
                .selectinload(VolunteerProfile.competency_assignments)
                .selectinload(VolunteerCompetencyAssignment.competency_item)
            )
            .filter(User.role == UserRole.VOLUNTEER)
        )

        if filters.q:
            like = f"%{filters.q.lower()}%"
            q = q.filter(
                or_(
                    func.lower(User.full_name).like(like),
                    func.lower(VolunteerProfile.about_me).like(like),
                )
            )
        if filters.city:
            q = q.filter(func.lower(VolunteerProfile.location_city) == filters.city.lower())

        if filters.animal_category and filters.animal_category != "all":
            cat = filters.animal_category.lower()
            needle = f'%"{cat}"%'
            q = q.filter(
                or_(
                    VolunteerProfile.animal_types_json.is_(None),
                    VolunteerProfile.animal_types_json == "",
                    VolunteerProfile.animal_types_json == "[]",
                    VolunteerProfile.animal_types_json.like(needle),
                )
            )

        for cid in filters.competencies:
            q = q.filter(_profile_has_competency_slug(cid))

        if filters.has_transport is True:
            q = q.filter(_profile_has_competency_slug("auto"))
        elif filters.has_transport is False:
            q = q.filter(~_profile_has_competency_slug("auto"))

        rows: list[tuple[User, VolunteerProfile]] = q.all()

        if filters.nearby and filters.latitude is not None and filters.longitude is not None:
            kept: list[tuple[User, VolunteerProfile]] = []
            for user, profile in rows:
                if profile.latitude is None or profile.longitude is None:
                    continue
                dist = _haversine_km(
                    filters.latitude,
                    filters.longitude,
                    float(profile.latitude),
                    float(profile.longitude),
                )
                if dist <= filters.radius_km:
                    kept.append((user, profile))
            rows = kept

        total = len(rows)

        sort_by = filters.sort_by or "name"
        if sort_by == "city":
            rows.sort(key=lambda r: (r[1].location_city or "", r[0].id))
        elif sort_by == "available_first":
            rows.sort(
                key=lambda r: (
                    not r[1].is_available,
                    -(r[1].completed_tasks_count or 0),
                    r[0].full_name or "",
                    r[0].id,
                )
            )
        else:
            rows.sort(key=lambda r: (r[0].full_name or "", r[0].id))

        chunk = rows[filters.offset : filters.offset + filters.limit]
        return total, chunk
