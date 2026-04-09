from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnimalSex(str, Enum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class AnimalStatus(str, Enum):
    LOOKING_FOR_HOME = "looking_for_home"
    IN_SHELTER = "in_shelter"
    ON_TREATMENT = "on_treatment"
    ADOPTED = "adopted"
    ARCHIVED = "archived"


class Animal(Base):
    __tablename__ = "animals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    sex: Mapped[AnimalSex] = mapped_column(String(20), default=AnimalSex.UNKNOWN.value)
    age_months: Mapped[int] = mapped_column(Integer, default=0)
    short_story: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    character_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_city: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default=AnimalStatus.IN_SHELTER.value, index=True)
    help_options: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    photos: Mapped[list["AnimalPhoto"]] = relationship(
        "AnimalPhoto", back_populates="animal", cascade="all, delete-orphan"
    )


class AnimalPhoto(Base):
    __tablename__ = "animal_photos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    animal: Mapped[Animal] = relationship("Animal", back_populates="photos")
