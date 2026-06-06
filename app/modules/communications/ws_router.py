from __future__ import annotations

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from starlette.websockets import WebSocketState

from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.user import User
from app.modules.communications.runtime import get_connection_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["communications"])


def _authenticate_ws_user(token: str, db) -> User:
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise PermissionError("Invalid or expired token") from exc
    if payload.get("type") != "access":
        raise PermissionError("Invalid token type")
    sub = payload.get("sub")
    if not sub:
        raise PermissionError("Invalid token subject")
    user = db.query(User).filter(User.id == int(sub)).first()
    if user is None:
        raise PermissionError("User not found")
    return user


async def _close_ws(websocket: WebSocket, code: int, reason: str) -> None:
    if websocket.client_state == WebSocketState.CONNECTING:
        await websocket.accept()
    await websocket.close(code=code, reason=reason)


@router.websocket("/ws/communications")
async def communications_websocket(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
) -> None:
    db = SessionLocal()
    try:
        user = _authenticate_ws_user(token, db)
    except PermissionError as exc:
        db.close()
        await _close_ws(websocket, status.WS_1008_POLICY_VIOLATION, str(exc))
        return
    finally:
        db.close()

    manager = get_connection_manager()
    await manager.connect(user.id, websocket)
    try:
        await websocket.send_json({"type": "connected", "user_id": user.id})
        while True:
            data = await websocket.receive_json()
            if not isinstance(data, dict):
                continue
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("WebSocket session ended for user_id=%s", user.id, exc_info=True)
    finally:
        await manager.disconnect(user.id, websocket)
