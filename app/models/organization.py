from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    city: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    region: Mapped[str | None] = mapped_column(String(160), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    specialization: Mapped[str] = mapped_column(
        String(20), default="both", index=True
    )
    needs_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    wards_count: Mapped[int] = mapped_column(Integer, default=0)
    adopted_yearly_count: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tagline: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    social_links_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    admission_rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    adoption_howto: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_organization: Mapped[bool] = mapped_column(Boolean, default=False)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    about_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    gallery_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    inn: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ogrn: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(64), nullable=True)
    help_sections_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_chat_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    animals: Mapped[list["Animal"]] = relationship("Animal", back_populates="organization")
    reports: Mapped[list["OrganizationReport"]] = relationship(
        "OrganizationReport", back_populates="organization", cascade="all, delete-orphan"
    )
    home_stories: Mapped[list["OrganizationHomeStory"]] = relationship(
        "OrganizationHomeStory", back_populates="organization", cascade="all, delete-orphan"
    )
