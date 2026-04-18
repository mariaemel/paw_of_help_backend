from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    """Публичная карточка организации для каталога (фонды, приюты)."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    city: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    specialization: Mapped[str] = mapped_column(
        String(20), default="both", index=True
    )  # cat | dog | both
    needs_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list[str]
    wards_count: Mapped[int] = mapped_column(Integer, default=0)
    adopted_yearly_count: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    animals: Mapped[list["Animal"]] = relationship("Animal", back_populates="organization")
