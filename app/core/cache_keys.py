from __future__ import annotations

import hashlib
import json

from app.modules.animals.schemas import AnimalFilterParams

ANIMALS_CATALOGS = "animals:catalogs"
KNOWLEDGE_CATALOGS = "knowledge:catalogs"
EVENTS_CATALOGS = "events:catalogs"
ORGANIZATIONS_CATALOGS = "organizations:catalogs"


def animals_list_key(filters: AnimalFilterParams) -> str:
    payload = filters.model_dump(mode="json")
    payload["features"] = sorted(payload.get("features") or [])
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"animals:list:{digest}"


def knowledge_article_key(article_id: int) -> str:
    return f"knowledge:article:{article_id}"


def organization_public_key(organization_id: int) -> str:
    return f"organizations:public:{organization_id}"
