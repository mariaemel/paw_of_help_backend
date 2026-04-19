from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.animal import Animal


class AnimalCatalogItem(Base):
    __tablename__ = "animal_catalog_items"
    __table_args__ = (UniqueConstraint("kind", "slug", name="uq_animal_catalog_kind_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    slug: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(255))
    keywords_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    assignments: Mapped[list[AnimalCatalogAssignment]] = relationship(
        "AnimalCatalogAssignment", back_populates="catalog_item", cascade="all, delete-orphan"
    )


class AnimalCatalogAssignment(Base):

    __tablename__ = "animal_catalog_assignments"
    __table_args__ = (UniqueConstraint("animal_id", "catalog_item_id", name="uq_animal_cat_assign_animal_item"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id", ondelete="CASCADE"), index=True)
    catalog_item_id: Mapped[int] = mapped_column(
        ForeignKey("animal_catalog_items.id", ondelete="RESTRICT"), index=True
    )

    animal: Mapped[Animal] = relationship("Animal", back_populates="catalog_assignments")
    catalog_item: Mapped[AnimalCatalogItem] = relationship("AnimalCatalogItem", back_populates="assignments")
