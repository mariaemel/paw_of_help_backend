from __future__ import annotations

from datetime import datetime

from app.models.org_chat import OrgChatDialog, OrgChatMessage
from app.modules.account import schemas as s
from app.modules.account.repository import AccountRepository
from app.modules.communications.broker import CommsEventBroker


def _dialog_unread_for_viewer(
    dialog: OrgChatDialog,
    viewer_user_id: int,
    org_owner_id: int | None,
    participant_id: int | None,
    repo: AccountRepository,
) -> int:
    if org_owner_id is not None and viewer_user_id == org_owner_id:
        return int(dialog.unread_count_org or 0)
    if participant_id is not None and viewer_user_id == participant_id:
        if repo.participant_is_volunteer(viewer_user_id):
            return int(dialog.unread_count_volunteer or 0)
        return int(dialog.unread_count_user or 0)
    return 0


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


class CommunicationsNotifier:
    def __init__(self, broker: CommsEventBroker) -> None:
        self._broker = broker

    def notify_new_message(
        self,
        *,
        dialog: OrgChatDialog,
        msg: OrgChatMessage,
        repo: AccountRepository,
        media_url_fn,
    ) -> None:
        org_owner_id = repo.get_organization_owner_user_id(dialog.organization_id)
        participant_id = dialog.participant_user_id

        recipient_ids: set[int] = set()
        if org_owner_id is not None:
            recipient_ids.add(org_owner_id)
        if participant_id is not None:
            recipient_ids.add(participant_id)

        if not recipient_ids:
            return

        for user_id in recipient_ids:
            is_outgoing = msg.sender_user_id == user_id
            item = s.OrgCommsMessageItem(
                id=msg.id,
                sender_user_id=msg.sender_user_id,
                sender_role=msg.sender_role,
                body=msg.body,
                photo_url=media_url_fn(msg.photo_path),
                created_at=msg.created_at,
                is_outgoing=is_outgoing,
            )
            payload = {
                "type": "message.new",
                "dialog_id": dialog.id,
                "message": item.model_dump(mode="json"),
                "dialog": {
                    "id": dialog.id,
                    "last_message_preview": dialog.last_message_preview,
                    "last_message_at": _iso(dialog.last_message_at),
                    "unread_count": _dialog_unread_for_viewer(
                        dialog, user_id, org_owner_id, participant_id, repo
                    ),
                },
            }
            self._broker.schedule_deliver(user_id, payload)
