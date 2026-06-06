from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod

from app.modules.communications.ws_manager import ConnectionManager

logger = logging.getLogger(__name__)

REDIS_CHANNEL = "paw:comms:ws"


class CommsEventBroker(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def deliver(self, user_id: int, payload: dict) -> None: ...

    def schedule_deliver(self, user_id: int, payload: dict) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("No running event loop; skipped WS delivery for user_id=%s", user_id)
            return
        loop.create_task(self.deliver(user_id, payload))


class LocalCommsEventBroker(CommsEventBroker):

    def __init__(self, manager: ConnectionManager) -> None:
        self._manager = manager

    async def start(self) -> None:
        return

    async def stop(self) -> None:
        return

    async def deliver(self, user_id: int, payload: dict) -> None:
        await self._manager.send_json(user_id, payload)


class RedisCommsEventBroker(CommsEventBroker):


    def __init__(self, redis_url: str, manager: ConnectionManager) -> None:
        self._redis_url = redis_url
        self._manager = manager
        self._redis = None
        self._listener_task: asyncio.Task | None = None

    async def start(self) -> None:
        from redis.asyncio import Redis

        self._redis = Redis.from_url(self._redis_url, decode_responses=True)
        self._listener_task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def deliver(self, user_id: int, payload: dict) -> None:
        if self._redis is None:
            return
        envelope = json.dumps({"user_id": user_id, "payload": payload}, ensure_ascii=False)
        await self._redis.publish(REDIS_CHANNEL, envelope)

    async def _listen(self) -> None:
        assert self._redis is not None
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(REDIS_CHANNEL)
        try:
            async for raw in pubsub.listen():
                if raw.get("type") != "message":
                    continue
                try:
                    data = json.loads(raw["data"])
                    user_id = int(data["user_id"])
                    payload = data["payload"]
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    logger.warning("Invalid WS envelope from Redis: %r", raw.get("data"))
                    continue
                await self._manager.send_json(user_id, payload)
        except asyncio.CancelledError:
            raise
        finally:
            await pubsub.unsubscribe(REDIS_CHANNEL)
            await pubsub.aclose()


def create_comms_broker(redis_url: str | None, manager: ConnectionManager) -> CommsEventBroker:
    if redis_url:
        return RedisCommsEventBroker(redis_url, manager)
    return LocalCommsEventBroker(manager)
