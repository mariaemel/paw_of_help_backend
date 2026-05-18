from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AdoptionApplicationStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class AnimalAdoptionApplication(Base):
    __tablename__ = "animal_adoption_applications"
    __table_args__ = (UniqueConstraint("user_id", "animal_id", name="uq_adoption_application_user_animal"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), index=True)
    status: Mapped[str] = mapped_column(
        String(32), default=AdoptionApplicationStatus.PENDING_REVIEW.value, index=True
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    applicant_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    applicant_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    applicant_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    applicant_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    housing_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    housing_ownership: Mapped[str | None] = mapped_column(String(20), nullable=True)
    residents_consent: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_children: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_allergy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    had_pets_before: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_pets_now: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    pet_experience: Mapped[str | None] = mapped_column(Text, nullable=True)

    why_now: Mapped[str | None] = mapped_column(Text, nullable=True)
    who_looking_for: Mapped[str | None] = mapped_column(Text, nullable=True)

    ready_for_vet_costs: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    feeding_plan: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ready_for_vaccination: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    time_to_devote: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vacation_care: Mapped[str | None] = mapped_column(String(500), nullable=True)
    return_plan: Mapped[str | None] = mapped_column(Text, nullable=True)

    ready_to_sign_contract: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ready_to_show_conditions: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ready_to_keep_in_touch: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="adoption_applications")
    animal = relationship("Animal", back_populates="adoption_applications")
