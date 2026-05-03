from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrganizationHomeStory(Base):
    __tablename__ = "organization_home_stories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    animal_name: Mapped[str] = mapped_column(String(120), index=True)
    story: Mapped[str] = mapped_column(Text)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    adopted_at: Mapped[date] = mapped_column(Date, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="home_stories")

