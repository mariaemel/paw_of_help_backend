from __future__ import annotations

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.animal import Animal, AnimalStatus
from app.models.help_request import HelpRequest
from app.modules.urgent.schemas import FUNDRAISING_HELP_TYPE_IDS


class HelpRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_candidate_animals(self, organization_id: int | None = None) -> list[Animal]:
        q = (
            self.db.query(Animal)
            .options(
                joinedload(Animal.organization),
                joinedload(Animal.photos),
                selectinload(Animal.help_requests),
            )
            .filter(Animal.status != AnimalStatus.ARCHIVED.value)
        )
        if organization_id is not None:
            q = q.filter(Animal.organization_id == organization_id)
        return q.order_by(Animal.id.asc()).all()

    def list_orphan_fundraising_requests(self, organization_id: int | None = None) -> list[HelpRequest]:
        q = (
            self.db.query(HelpRequest)
            .options(joinedload(HelpRequest.organization))
            .filter(
                HelpRequest.animal_id.is_(None),
                HelpRequest.is_archived.is_(False),
                HelpRequest.is_published.is_(True),
                HelpRequest.help_type.in_(tuple(FUNDRAISING_HELP_TYPE_IDS)),
                HelpRequest.status.in_(("open", "in_progress")),
            )
        )
        if organization_id is not None:
            q = q.filter(HelpRequest.organization_id == organization_id)
        return q.order_by(HelpRequest.is_urgent.desc(), HelpRequest.id.desc()).all()

    def list_public_fundraising_requests(self, organization_id: int | None = None) -> list[HelpRequest]:
        q = (
            self.db.query(HelpRequest)
            .options(
                joinedload(HelpRequest.organization),
                joinedload(HelpRequest.animal).joinedload(Animal.photos),
            )
            .filter(
                HelpRequest.is_archived.is_(False),
                HelpRequest.is_published.is_(True),
                HelpRequest.help_type.in_(tuple(FUNDRAISING_HELP_TYPE_IDS)),
                HelpRequest.status.in_(("open", "in_progress")),
            )
        )
        if organization_id is not None:
            q = q.filter(HelpRequest.organization_id == organization_id)
        return q.order_by(HelpRequest.is_urgent.desc(), HelpRequest.id.desc()).all()
