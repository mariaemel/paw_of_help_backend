from __future__ import annotations

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.animal import Animal, AnimalStatus


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
