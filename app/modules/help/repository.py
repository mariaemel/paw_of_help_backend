from __future__ import annotations

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.animal import Animal, AnimalStatus


class HelpRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_candidate_animals(self) -> list[Animal]:
        return (
            self.db.query(Animal)
            .options(
                joinedload(Animal.organization),
                joinedload(Animal.photos),
                selectinload(Animal.help_requests),
            )
            .filter(Animal.status != AnimalStatus.ARCHIVED.value)
            .order_by(Animal.id.asc())
            .all()
        )
