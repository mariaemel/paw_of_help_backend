from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.volunteer_help_response import VolunteerHelpResponse


class HelpRequest(Base):
    __tablename__ = "help_requests"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    help_type: Mapped[str] = mapped_column(String(40), index=True)
    urgency_level: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    volunteer_needed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    volunteer_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    volunteer_competencies_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    collected_amount: Mapped[float] = mapped_column(Float, default=0.0)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    deadline_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization")
    animal = relationship("Animal", back_populates="help_requests")
    volunteer_responses: Mapped[list["VolunteerHelpResponse"]] = relationship(
        "VolunteerHelpResponse", back_populates="help_request", cascade="all, delete-orphan"
    )
