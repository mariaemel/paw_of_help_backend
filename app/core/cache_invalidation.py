from __future__ import annotations

from app.core import cache
from app.core.cache_keys import (
    ANIMALS_CATALOGS,
    EVENTS_CATALOGS,
    KNOWLEDGE_CATALOGS,
    ORGANIZATIONS_CATALOGS,
    knowledge_article_key,
    organization_public_key,
)


def invalidate_animals_cache() -> None:
    """Сброс справочников и списков каталога животных."""
    cache.delete(ANIMALS_CATALOGS)
    cache.delete_prefix("animals:list:")


def invalidate_knowledge_article(article_id: int) -> None:
    cache.delete(knowledge_article_key(article_id))


def invalidate_organization_public(organization_id: int) -> None:
    cache.delete(organization_public_key(organization_id))
    cache.delete(ORGANIZATIONS_CATALOGS)


def invalidate_events_catalogs() -> None:
    cache.delete(EVENTS_CATALOGS)
