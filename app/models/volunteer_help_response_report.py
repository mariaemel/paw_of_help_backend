from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.volunteer_help_response import VolunteerHelpResponse


class VolunteerHelpResponseReport(Base):
    __tablename__ = "volunteer_help_response_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    volunteer_help_response_id: Mapped[int] = mapped_column(
        ForeignKey("volunteer_help_responses.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    body: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    org_accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    org_rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    response: Mapped["VolunteerHelpResponse"] = relationship("VolunteerHelpResponse", back_populates="report")
