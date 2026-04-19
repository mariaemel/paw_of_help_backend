from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.profile import VolunteerProfile


class VolunteerCompetencyItem(Base):

    __tablename__ = "volunteer_competency_items"
    __table_args__ = (UniqueConstraint("slug", name="uq_volunteer_competency_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    assignments: Mapped[list["VolunteerCompetencyAssignment"]] = relationship(
        "VolunteerCompetencyAssignment", back_populates="competency_item"
    )


class VolunteerCompetencyAssignment(Base):
    __tablename__ = "volunteer_competency_assignments"
    __table_args__ = (
        UniqueConstraint("volunteer_profile_id", "competency_item_id", name="uq_vol_prof_comp_item"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    volunteer_profile_id: Mapped[int] = mapped_column(
        ForeignKey("volunteer_profiles.id", ondelete="CASCADE"), index=True
    )
    competency_item_id: Mapped[int] = mapped_column(
        ForeignKey("volunteer_competency_items.id", ondelete="RESTRICT"), index=True
    )

    volunteer_profile: Mapped["VolunteerProfile"] = relationship(
        "VolunteerProfile", back_populates="competency_assignments"
    )
    competency_item: Mapped[VolunteerCompetencyItem] = relationship(
        "VolunteerCompetencyItem", back_populates="assignments"
    )
