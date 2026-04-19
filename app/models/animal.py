from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.animal_catalog import AnimalCatalogAssignment
    from app.models.organization import Organization


class AnimalSex(str, Enum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class AnimalSpecies(str, Enum):
    CAT = "cat"
    DOG = "dog"
    OTHER = "other"


class AnimalStatus(str, Enum):
    LOOKING_FOR_HOME = "looking_for_home"
    IN_SHELTER = "in_shelter"
    ON_TREATMENT = "on_treatment"
    LOOKING_FOR_FOSTER = "looking_for_foster"
    ADOPTED = "adopted"
    ARCHIVED = "archived"


class Animal(Base):
    __tablename__ = "animals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True, nullable=True)

    name: Mapped[str] = mapped_column(String(120), index=True)
    species: Mapped[str] = mapped_column(String(20), default=AnimalSpecies.CAT.value, index=True)
    breed: Mapped[str | None] = mapped_column(String(120), nullable=True)

    sex: Mapped[str] = mapped_column(String(20), default=AnimalSex.UNKNOWN.value)
    age_months: Mapped[int] = mapped_column(Integer, default=0)

    full_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    health_features: Mapped[str | None] = mapped_column(Text, nullable=True)
    treatment_required: Mapped[str | None] = mapped_column(Text, nullable=True)

    location_city: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    urgent_needs_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(40), default=AnimalStatus.IN_SHELTER.value, index=True)
    help_options: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    photos: Mapped[list["AnimalPhoto"]] = relationship(
        "AnimalPhoto", back_populates="animal", cascade="all, delete-orphan"
    )
    catalog_assignments: Mapped[list["AnimalCatalogAssignment"]] = relationship(
        "AnimalCatalogAssignment",
        back_populates="animal",
        cascade="all, delete-orphan",
    )
    organization: Mapped[Organization | None] = relationship("Organization", back_populates="animals")


class AnimalPhoto(Base):
    __tablename__ = "animal_photos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    animal: Mapped[Animal] = relationship("Animal", back_populates="photos")
