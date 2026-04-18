import json
import math

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

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
        ]
        return cities, specs, needs_opts

    def list_organizations(self, filters: OrganizationFilterParams) -> tuple[int, list[Organization]]:
        q = self.db.query(Organization)

        if filters.q:
            like = f"%{filters.q.lower()}%"
            q = q.filter(
                or_(func.lower(Organization.name).like(like), func.lower(Organization.description).like(like))
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
