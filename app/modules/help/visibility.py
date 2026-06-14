from __future__ import annotations

from app.models.help_request import HelpRequest
from app.modules.urgent.schemas import FUNDRAISING_HELP_TYPE_IDS

_PUBLIC_ACTIVE_STATUSES = frozenset({"open", "in_progress"})


def normalize_help_request_status(status: str | None) -> str:
    return (status or "open").strip().lower()


def is_public_listable(hr: HelpRequest) -> bool:
    if hr.is_archived or not hr.is_published:
        return False
    return normalize_help_request_status(hr.status) in _PUBLIC_ACTIVE_STATUSES


def is_public_fundraising(hr: HelpRequest) -> bool:
    if not is_public_listable(hr):
        return False
    help_type = (hr.help_type or "").strip().lower()
    return help_type in FUNDRAISING_HELP_TYPE_IDS
