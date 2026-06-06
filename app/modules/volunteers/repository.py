from sqlalchemy import asc, desc, exists, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.geo import filter_sort_paginate_nearby
from app.core.list_query import apply_city_filter, apply_text_search, geo_bbox_clauses
from app.models.knowledge import KnowledgeArticle
from app.models.profile import VolunteerProfile
from app.models.user import User, UserRole
from app.models.volunteer_competency import VolunteerCompetencyAssignment, VolunteerCompetencyItem
from app.modules.volunteers.schemas import VolunteerFilterParams


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
                joinedload(User.user_profile),
                selectinload(User.volunteer_profile)
                .selectinload(VolunteerProfile.competency_assignments)
                .selectinload(VolunteerCompetencyAssignment.competency_item),
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

    def _list_volunteers_query(self, filters: VolunteerFilterParams):
        q = (
            self.db.query(User, VolunteerProfile)
            .join(VolunteerProfile, VolunteerProfile.user_id == User.id)
            .filter(User.role == UserRole.VOLUNTEER)
        )
        q = apply_text_search(q, filters.q, User.full_name, VolunteerProfile.about_me)
        q = apply_city_filter(q, VolunteerProfile.location_city, filters.city)

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

        return q

    def list_volunteers(self, filters: VolunteerFilterParams) -> tuple[int, list[tuple[User, VolunteerProfile]]]:
        q = self._list_volunteers_query(filters)
        load_opts = (
            joinedload(User.user_profile),
            selectinload(User.volunteer_profile)
            .selectinload(VolunteerProfile.competency_assignments)
            .selectinload(VolunteerCompetencyAssignment.competency_item),
        )

        if filters.nearby and filters.latitude is not None and filters.longitude is not None:
            radius = filters.radius_km or 50.0
            q = q.filter(
                *geo_bbox_clauses(
                    VolunteerProfile.latitude, VolunteerProfile.longitude, filters.latitude, filters.longitude, radius
                )
            )
            candidates: list[tuple[User, VolunteerProfile]] = q.options(load_opts).all()

            sort_by = filters.sort_by or "name"
            if sort_by == "city":
                sort_fn = lambda r: (r[1].location_city or "", r[0].id)
            elif sort_by == "available_first":
                sort_fn = lambda r: (
                    not r[1].is_available,
                    -(r[1].completed_tasks_count or 0),
                    (r[0].full_name or "").lower(),
                    r[0].id,
                )
            else:
                sort_fn = lambda r: ((r[0].full_name or "").lower(), r[0].id)

            return filter_sort_paginate_nearby(
                candidates,
                center_lat=filters.latitude,
                center_lon=filters.longitude,
                radius_km=radius,
                get_lat_lon=lambda r: (r[1].latitude, r[1].longitude),
                sort_key=sort_fn,
                offset=filters.offset,
                limit=filters.limit,
            )

        total = q.order_by(None).count()
        sort_by = filters.sort_by or "name"
        if sort_by == "city":
            q = q.order_by(asc(VolunteerProfile.location_city), asc(User.full_name), asc(User.id))
        elif sort_by == "available_first":
            q = q.order_by(
                desc(VolunteerProfile.is_available),
                desc(VolunteerProfile.completed_tasks_count),
                asc(User.full_name),
                asc(User.id),
            )
        else:
            q = q.order_by(asc(User.full_name), asc(User.id))

        rows = q.options(load_opts).offset(filters.offset).limit(filters.limit).all()
        return total, rows
