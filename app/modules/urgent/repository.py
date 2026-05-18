from sqlalchemy import asc, desc
from sqlalchemy.orm import Session, joinedload

from app.core.list_query import apply_city_filter, apply_text_search
from app.models.animal import Animal
from app.models.help_request import HelpRequest
from app.models.organization import Organization
from app.modules.urgent.schemas import UrgentFilterParams


class UrgentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_organization(self, organization_id: int) -> Organization | None:
        return self.db.query(Organization).filter(Organization.id == organization_id).first()

    def get_animal(self, animal_id: int) -> Animal | None:
        return self.db.query(Animal).filter(Animal.id == animal_id).first()

    def get_request(self, request_id: int) -> HelpRequest | None:
        return (
            self.db.query(HelpRequest)
            .options(joinedload(HelpRequest.organization), joinedload(HelpRequest.animal).joinedload(Animal.photos))
            .filter(
                HelpRequest.id == request_id,
                HelpRequest.is_archived.is_(False),
                HelpRequest.is_published.is_(True),
            )
            .first()
        )

    def get_request_for_owner(self, request_id: int) -> HelpRequest | None:
        return (
            self.db.query(HelpRequest)
            .options(joinedload(HelpRequest.organization), joinedload(HelpRequest.animal).joinedload(Animal.photos))
            .filter(HelpRequest.id == request_id)
            .first()
        )

    def list_catalogs(self) -> tuple[list[str], list[str]]:
        cities = [
            row[0]
            for row in self.db.query(HelpRequest.city).distinct().order_by(HelpRequest.city.asc()).all()
            if row[0]
        ]
        species = [
            row[0]
            for row in self.db.query(Animal.species)
            .join(HelpRequest, HelpRequest.animal_id == Animal.id)
            .distinct()
            .order_by(Animal.species.asc())
            .all()
            if row[0]
        ]
        return cities, species

    def _list_public_urgent_query(self, filters: UrgentFilterParams):
        q = self.db.query(HelpRequest).filter(
            HelpRequest.is_archived.is_(False),
            HelpRequest.is_published.is_(True),
            HelpRequest.is_urgent.is_(True),
        )
        q = apply_text_search(q, filters.q, HelpRequest.title, HelpRequest.description)
        q = apply_city_filter(q, HelpRequest.city, filters.city)
        if filters.help_types:
            q = q.filter(HelpRequest.help_type.in_(filters.help_types))
        if filters.animal_species and filters.animal_species != "all":
            q = q.join(Animal, Animal.id == HelpRequest.animal_id).filter(Animal.species == filters.animal_species)
        return q

    def list_public_urgent(self, filters: UrgentFilterParams) -> tuple[int, list[HelpRequest]]:
        q = self._list_public_urgent_query(filters)
        total = q.order_by(None).count()

        if filters.sort_by == "deadline":
            q = q.order_by(
                asc(HelpRequest.deadline_at.is_(None)),
                asc(HelpRequest.deadline_at),
                desc(HelpRequest.id),
            )
        else:
            q = q.order_by(desc(HelpRequest.created_at), desc(HelpRequest.id))

        rows = (
            q.options(
                joinedload(HelpRequest.organization),
                joinedload(HelpRequest.animal).joinedload(Animal.photos),
            )
            .offset(filters.offset)
            .limit(filters.limit)
            .all()
        )
        return total, rows
