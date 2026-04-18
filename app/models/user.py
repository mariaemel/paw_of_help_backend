from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, Enum):
    USER = "user"
    VOLUNTEER = "volunteer"
    ORGANIZATION = "organization"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(SqlEnum(UserRole), default=UserRole.USER)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user_profile: Mapped["UserProfile | None"] = relationship(
        "UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    volunteer_profile: Mapped["VolunteerProfile | None"] = relationship(
        "VolunteerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    organization_profile: Mapped["OrganizationProfile | None"] = relationship(
        "OrganizationProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    verification_tokens: Mapped[list["VerificationToken"]] = relationship(
        "VerificationToken", back_populates="user", cascade="all, delete-orphan"
    )
    volunteer_reviews_received: Mapped[list["VolunteerReview"]] = relationship(
        "VolunteerReview",
        foreign_keys="VolunteerReview.volunteer_user_id",
        back_populates="volunteer",
        cascade="all, delete-orphan",
    )
