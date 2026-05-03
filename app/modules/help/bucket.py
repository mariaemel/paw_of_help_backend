from __future__ import annotations

from app.models.help_request import HelpRequest


def help_bucket_for_request(hr: HelpRequest) -> str | None:
    if not hr.is_published or hr.is_archived:
        return None
    if hr.animal_id is None:
        return None

    t = (hr.help_type or "").strip().lower()
    if t == "medical":
        return "heal"
    if t == "food":
        return "feed"
    if t == "financial":
        blob = f"{hr.title}\n{hr.description}".lower()
        if any(k in blob for k in ("операц", "лечен", "клиник", "медиц", "стационар", "лап")):
            return "heal"
        if any(k in blob for k in ("корм", "гастро", "пащтет", "кормление")):
            return "feed"
        return "other"
    if t in ("manual", "auto", "foster"):
        return "other"
    return None
