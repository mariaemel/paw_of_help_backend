from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrganizationVerificationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="user_profile")


class VolunteerProfile(Base):
    __tablename__ = "volunteer_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)

    skills: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    about_me: Mapped[str | None] = mapped_column(Text, nullable=True)
    availability: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    travel_radius_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preferred_help_format: Mapped[str | None] = mapped_column(String(120), nullable=True)
    animal_categories: Mapped[str | None] = mapped_column(Text, nullable=True)
    animal_types_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    competencies_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    avatar_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    rating: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    completed_tasks_count: Mapped[int] = mapped_column(Integer, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="volunteer_profile")


class VolunteerReview(Base):
    __tablename__ = "volunteer_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    volunteer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    author_name: Mapped[str] = mapped_column(String(255))
    author_avatar_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    review_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    volunteer: Mapped["User"] = relationship(
        "User", foreign_keys=[volunteer_user_id], back_populates="volunteer_reviews_received"
    )


class OrganizationProfile(Base):
    __tablename__ = "organization_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)

    display_name: Mapped[str] = mapped_column(String(255))
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work_territory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    admission_rules: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="organization_profile")
    contacts: Mapped[list["OrganizationContact"]] = relationship(
        "OrganizationContact", back_populates="organization", cascade="all, delete-orphan"
    )
    verification: Mapped["OrganizationVerification | None"] = relationship(
        "OrganizationVerification",
        back_populates="organization",
        uselist=False,
        cascade="all, delete-orphan",
    )


class OrganizationContact(Base):
    __tablename__ = "organization_contacts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organization_profiles.id"), index=True)

    contact_type: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(String(255))
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped[OrganizationProfile] = relationship("OrganizationProfile", back_populates="contacts")


class OrganizationVerification(Base):
    __tablename__ = "organization_verifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organization_profiles.id"), unique=True, index=True)

    status: Mapped[str] = mapped_column(String(30), default=OrganizationVerificationStatus.PENDING.value)
    documents_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization: Mapped[OrganizationProfile] = relationship("OrganizationProfile", back_populates="verification")
