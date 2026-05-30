from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.volunteer_help_response_report import VolunteerHelpResponseReport


class VolunteerHelpResponseReportPhoto(Base):
    __tablename__ = "volunteer_help_response_report_photos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("volunteer_help_response_reports.id", ondelete="CASCADE"),
        index=True,
    )
    file_path: Mapped[str] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    report: Mapped["VolunteerHelpResponseReport"] = relationship(
        "VolunteerHelpResponseReport",
        back_populates="photos",
    )
