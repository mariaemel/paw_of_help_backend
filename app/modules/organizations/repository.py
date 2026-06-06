from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.geo import filter_sort_paginate_nearby
from app.core.list_query import apply_city_filter, apply_text_search, geo_bbox_clauses
from app.models.animal import Animal
from app.models.event import Event
from app.models.help_request import HelpRequest
from app.models.knowledge import KnowledgeArticle
from app.models.organization_home_story import OrganizationHomeStory
from app.models.organization_report import OrganizationReport
from app.models.organization import Organization
from app.modules.organizations.schemas import OrganizationFilterParams


class OrganizationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_organization_catalogs(self) -> tuple[list[str], list[str], list[dict[str, str]]]:
        cities = [
            row[0]
            for row in self.db.query(Organization.city)
            .distinct()
            .order_by(Organization.city.asc())
            .all()
            if row[0]
        ]
        specs = ["cat", "dog", "both"]
        needs_opts = [
            {"id": "urgent", "label": "Срочно"},
            {"id": "volunteers", "label": "Нужны волонтёры"},
            {"id": "foster", "label": "Нужна передержка"},
            {"id": "financial", "label": "Финансовая помощь"},
            {"id": "items", "label": "Помощь вещами / кормом"},
            {"id": "auto", "label": "Автопомощь"},
            {"id": "fundraising", "label": "Сбор"},
        ]
        return cities, specs, needs_opts

    def _list_organizations_query(self, filters: OrganizationFilterParams):
        q = self.db.query(Organization)
        q = apply_text_search(
            q,
            filters.q,
            Organization.name,
            Organization.tagline,
            Organization.description,
        )
        q = apply_city_filter(q, Organization.city, filters.city)
        if filters.specialization and filters.specialization != "all":
            if filters.specialization in ("cat", "dog"):
                q = q.filter(
                    Organization.specialization.in_((filters.specialization, "both"))
                )
        if filters.needs:
            for need in filters.needs:
                q = q.filter(Organization.needs_json.like(f'%"{need}"%'))
        return q

    def list_organizations(self, filters: OrganizationFilterParams) -> tuple[int, list[Organization]]:
        q = self._list_organizations_query(filters)

        if filters.nearby and filters.latitude is not None and filters.longitude is not None:
            radius = filters.radius_km or 50.0
            q = q.filter(
                *geo_bbox_clauses(
                    Organization.latitude, Organization.longitude, filters.latitude, filters.longitude, radius
                )
            )
            candidates = q.all()
            if filters.sort_by == "-wards":
                sort_fn = lambda o: (-(o.wards_count or 0), o.name.lower(), o.id)
            elif filters.sort_by == "city":
                sort_fn = lambda o: (o.city or "", o.name.lower(), o.id)
            else:
                sort_fn = lambda o: (o.name.lower(), o.id)

            return filter_sort_paginate_nearby(
                candidates,
                center_lat=filters.latitude,
                center_lon=filters.longitude,
                radius_km=radius,
                get_lat_lon=lambda o: (o.latitude, o.longitude),
                sort_key=sort_fn,
                offset=filters.offset,
                limit=filters.limit,
            )

        total = q.order_by(None).count()
        if filters.sort_by == "-wards":
            q = q.order_by(desc(Organization.wards_count), asc(Organization.name), asc(Organization.id))
        elif filters.sort_by == "city":
            q = q.order_by(asc(Organization.city), asc(Organization.name), asc(Organization.id))
        else:
            q = q.order_by(asc(Organization.name), asc(Organization.id))

        rows = q.offset(filters.offset).limit(filters.limit).all()
        return total, rows

    def get_owned_by_user(self, owner_user_id: int) -> Organization | None:
        return (
            self.db.query(Organization)
            .filter(Organization.owner_user_id == owner_user_id)
            .order_by(Organization.id.asc())
            .first()
        )

    def get_by_id(self, organization_id: int) -> Organization | None:
        return self.db.query(Organization).filter(Organization.id == organization_id).first()

    def list_public_wards(self, organization_id: int, limit: int = 240) -> list[Animal]:
        return (
            self.db.query(Animal)
            .options(joinedload(Animal.photos), selectinload(Animal.help_requests))
            .filter(
                Animal.organization_id == organization_id,
                Animal.status.notin_(("adopted", "archived")),
            )
            .order_by(Animal.is_urgent.desc(), Animal.id.asc())
            .limit(limit)
            .all()
        )

    def list_org_events(self, organization_id: int, limit: int = 50) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(
                Event.organization_id == organization_id,
                Event.is_published.is_(True),
                Event.is_archived.is_(False),
            )
            .order_by(Event.starts_at.asc())
            .limit(limit)
            .all()
        )

    def list_org_help_requests_open(self, organization_id: int, limit: int = 80) -> list[HelpRequest]:
        return (
            self.db.query(HelpRequest)
            .filter(
                HelpRequest.organization_id == organization_id,
                HelpRequest.is_published.is_(True),
                HelpRequest.is_archived.is_(False),
                HelpRequest.status == "open",
            )
            .order_by(HelpRequest.is_urgent.desc(), HelpRequest.created_at.desc())
            .limit(limit)
            .all()
        )

    def list_org_reports(self, organization_id: int, limit: int = 50) -> list[OrganizationReport]:
        return (
            self.db.query(OrganizationReport)
            .filter(
                OrganizationReport.organization_id == organization_id,
                OrganizationReport.is_published.is_(True),
            )
            .order_by(OrganizationReport.published_at.desc())
            .limit(limit)
            .all()
        )

    def list_org_home_stories(self, organization_id: int, limit: int = 50) -> list[OrganizationHomeStory]:
        return (
            self.db.query(OrganizationHomeStory)
            .filter(OrganizationHomeStory.organization_id == organization_id)
            .order_by(OrganizationHomeStory.adopted_at.desc(), OrganizationHomeStory.id.desc())
            .limit(limit)
            .all()
        )

    def list_org_articles_by_author(self, author_user_id: int, limit: int = 40) -> list[KnowledgeArticle]:
        return (
            self.db.query(KnowledgeArticle)
            .filter(
                KnowledgeArticle.author_user_id == author_user_id,
                func.lower(KnowledgeArticle.owner_role) == "organization",
                KnowledgeArticle.is_published.is_(True),
                KnowledgeArticle.is_archived.is_(False),
                KnowledgeArticle.is_context_tip.is_(False),
            )
            .order_by(KnowledgeArticle.created_at.desc())
            .limit(limit)
            .all()
        )
