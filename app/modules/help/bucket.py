from __future__ import annotations

from app.models.help_request import HelpRequest
from app.modules.urgent.schemas import FUNDRAISING_HELP_TYPE_IDS
from app.modules.volunteers.constants import COMPETENCY_OPTIONS

_FUNDRAISING_HELP_TYPES = FUNDRAISING_HELP_TYPE_IDS
_VOLUNTEER_TASK_HELP_TYPES = frozenset(x["id"] for x in COMPETENCY_OPTIONS)


def _published_fundraising_bucket(hr: HelpRequest) -> str | None:
    if not hr.is_published or hr.is_archived:
        return None
    if (hr.status or "").strip().lower() == "closed":
        return None

    t = (hr.help_type or "").strip().lower()
    if hr.volunteer_needed and t not in _FUNDRAISING_HELP_TYPES:
        return None

    if t == "medical":
        return "heal"
    if t in ("food", "feed"):
        return "feed"
    if t == "financial":
        blob = f"{hr.title}\n{hr.description}".lower()
        if any(k in blob for k in ("операц", "лечен", "клиник", "медиц", "стационар", "лап")):
            return "heal"
        if any(k in blob for k in ("корм", "гастро", "пащтет", "кормление")):
            return "feed"
        return "other"

    if t in _VOLUNTEER_TASK_HELP_TYPES:
        return None
    return None


def help_bucket_for_request(hr: HelpRequest) -> str | None:
    if hr.animal_id is None:
        return None
    return _published_fundraising_bucket(hr)


def help_bucket_for_orphan_request(hr: HelpRequest) -> str | None:
    if hr.animal_id is not None:
        return None
    return _published_fundraising_bucket(hr)
