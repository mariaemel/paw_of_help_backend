from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.volunteer_help_response_report import VolunteerHelpResponseReport


class VolunteerHelpResponseStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class VolunteerHelpResponse(Base):
    __tablename__ = "volunteer_help_responses"
    __table_args__ = (UniqueConstraint("volunteer_user_id", "help_request_id", name="uq_vol_help_resp_user_request"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    volunteer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    help_request_id: Mapped[int] = mapped_column(ForeignKey("help_requests.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default=VolunteerHelpResponseStatus.PENDING.value, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    volunteer = relationship("User", back_populates="volunteer_help_responses")
    help_request = relationship("HelpRequest", back_populates="volunteer_responses")
    report: Mapped["VolunteerHelpResponseReport | None"] = relationship(
        "VolunteerHelpResponseReport",
        back_populates="response",
        uselist=False,
        cascade="all, delete-orphan",
    )
