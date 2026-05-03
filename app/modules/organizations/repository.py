import json
import math

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.animal import Animal
from app.models.event import Event
from app.models.help_request import HelpRequest
from app.models.knowledge import KnowledgeArticle
from app.models.organization_home_story import OrganizationHomeStory
from app.models.organization_report import OrganizationReport
from app.models.organization import Organization
from app.modules.organizations.schemas import OrganizationFilterParams


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p = math.pi / 180
    a = (
        0.5
        - math.cos((lat2 - lat1) * p) / 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    )
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


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
            {"id": "volunteers", "label": "Нужны волонтеры"},
            {"id": "foster", "label": "Нужна передержка"},
            {"id": "financial", "label": "Финансовая помощь"},
            {"id": "items", "label": "Помощь вещами / кормом"},
            {"id": "auto", "label": "Автопомощь"},
            {"id": "fundraising", "label": "Сбор"},
        ]
        return cities, specs, needs_opts

    def list_organizations(self, filters: OrganizationFilterParams) -> tuple[int, list[Organization]]:
        q = self.db.query(Organization)

        if filters.q:
            like = f"%{filters.q.lower()}%"
            q = q.filter(
                or_(
                    func.lower(Organization.name).like(like),
                    func.lower(Organization.description).like(like),
                    func.lower(func.coalesce(Organization.tagline, "")).like(like),
                )
            )
        if filters.city:
            q = q.filter(func.lower(Organization.city) == filters.city.lower())
        if filters.specialization and filters.specialization != "all":
            if filters.specialization in ("cat", "dog"):
                q = q.filter(
                    or_(
                        Organization.specialization == filters.specialization,
                        Organization.specialization == "both",
                    )
                )

        rows = q.all()
        if filters.needs:
            filtered = []
            for org in rows:
                raw = org.needs_json or "[]"
                try:
                    arr = json.loads(raw)
                except json.JSONDecodeError:
                    arr = []
                if not isinstance(arr, list):
                    arr = []
                if all(n in arr for n in filters.needs):
                    filtered.append(org)
            rows = filtered

        if filters.nearby and filters.latitude is not None and filters.longitude is not None:
            nearby_rows = []
            rmax = filters.radius_km or 50.0
            for org in rows:
                if org.latitude is None or org.longitude is None:
                    continue
                d = _haversine_km(filters.latitude, filters.longitude, org.latitude, org.longitude)
                if d <= rmax:
                    nearby_rows.append(org)
            rows = nearby_rows

        total = len(rows)

        if filters.sort_by == "-wards":
            rows.sort(key=lambda o: o.wards_count, reverse=True)
        elif filters.sort_by == "city":
            rows.sort(key=lambda o: (o.city or "", o.name))
        else:
            rows.sort(key=lambda o: o.name.lower())

        chunk = rows[filters.offset : filters.offset + filters.limit]
        return total, chunk

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
            .order_by(
                OrganizationHomeStory.sort_order.asc(),
                OrganizationHomeStory.adopted_at.desc(),
            )
            .limit(limit)
            .all()
        )

    def list_org_articles_by_author(self, author_user_id: int, limit: int = 40) -> list[KnowledgeArticle]:
        return (
            self.db.query(KnowledgeArticle)
            .filter(
                KnowledgeArticle.author_user_id == author_user_id,
                KnowledgeArticle.owner_role == "organization",
                KnowledgeArticle.is_published.is_(True),
                KnowledgeArticle.is_archived.is_(False),
                KnowledgeArticle.is_context_tip.is_(False),
            )
            .order_by(KnowledgeArticle.created_at.desc())
            .limit(limit)
            .all()
        )
