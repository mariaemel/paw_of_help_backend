from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, status

_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
_WINDOW_SEC = 15 * 60
_MAX_FAILS = 5


def throttle_key(client_host: str | None, credential_normalized: str) -> str:
    host = (client_host or "unknown").strip() or "unknown"
    return f"{host}|{credential_normalized}"


def enforce_not_locked(key: str) -> None:
    now = time.monotonic()
    arr = _ATTEMPTS[key]
    arr[:] = [t for t in arr if now - t <= _WINDOW_SEC]
    if len(arr) >= _MAX_FAILS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много неудачных попыток входа. Повторите позже.",
        )


def record_failure(key: str) -> None:
    now = time.monotonic()
    arr = _ATTEMPTS[key]
    arr[:] = [t for t in arr if now - t <= _WINDOW_SEC]
    arr.append(now)


def clear_failures(key: str) -> None:
    _ATTEMPTS.pop(key, None)
