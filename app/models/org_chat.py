from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrgChatDialog(Base):
    __tablename__ = "org_chat_dialogs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    participant_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    participant_name: Mapped[str] = mapped_column(String(255))
    participant_avatar_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    context_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    context_entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_message_preview: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    unread_count_org: Mapped[int] = mapped_column(Integer, default=0)
    unread_count_volunteer: Mapped[int] = mapped_column(Integer, default=0)
    unread_count_user: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrgChatMessage(Base):
    __tablename__ = "org_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    dialog_id: Mapped[int] = mapped_column(ForeignKey("org_chat_dialogs.id"), index=True)
    sender_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    sender_role: Mapped[str] = mapped_column(String(40), index=True)
    body: Mapped[str] = mapped_column(Text)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    read_by_org_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    read_by_volunteer_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    read_by_user_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
