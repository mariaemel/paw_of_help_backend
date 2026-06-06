from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

PREFIX = "paw:cache:"
_client = None

T = TypeVar("T", bound=BaseModel)


def _full_key(key: str) -> str:
    if key.startswith(PREFIX):
        return key
    return f"{PREFIX}{key}"


def _get_client():
    global _client
    if not settings.redis_url:
        return None
    if _client is None:
        try:
            import redis
        except ImportError:
            logger.warning("REDIS_URL is set but package 'redis' is not installed (pip install redis)")
            return None
        try:
            _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            _client.ping()
        except Exception:
            logger.warning("Redis unavailable at %s", settings.redis_url, exc_info=True)
            _client = None
            return None
    return _client


def is_enabled() -> bool:
    return _get_client() is not None


def get_json(key: str) -> Any | None:
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(_full_key(key))
    except Exception:
        logger.warning("Redis GET failed for key=%s", key, exc_info=True)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in cache for key=%s", key)
        delete(key)
        return None


def set_json(key: str, value: Any, ttl_seconds: int) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(_full_key(key), ttl_seconds, json.dumps(value, ensure_ascii=False))
    except Exception:
        logger.warning("Redis SET failed for key=%s", key, exc_info=True)


def delete(key: str) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(_full_key(key))
    except Exception:
        logger.warning("Redis DELETE failed for key=%s", key, exc_info=True)


def delete_prefix(key_prefix: str) -> int:
    client = _get_client()
    if client is None:
        return 0
    pattern = _full_key(key_prefix) + "*"
    removed = 0
    try:
        for match in client.scan_iter(match=pattern, count=200):
            client.delete(match)
            removed += 1
    except Exception:
        logger.warning("Redis SCAN/DELETE failed for prefix=%s", key_prefix, exc_info=True)
    return removed


def cached_model(key: str, ttl_seconds: int, model: type[T], loader: Callable[[], T]) -> T:
    if is_enabled():
        raw = get_json(key)
        if raw is not None:
            try:
                return model.model_validate(raw)
            except Exception:
                logger.warning("Cache validation failed for key=%s", key, exc_info=True)
                delete(key)
    result = loader()
    if is_enabled():
        set_json(key, result.model_dump(mode="json"), ttl_seconds)
    return result
