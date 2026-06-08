from __future__ import annotations

import asyncio

from app.core.config import settings
from app.modules.communications.broker import CommsEventBroker, create_comms_broker
from app.modules.communications.notifier import CommunicationsNotifier
from app.modules.communications.ws_manager import ConnectionManager

_manager = ConnectionManager()
_broker: CommsEventBroker | None = None
_notifier: CommunicationsNotifier | None = None
_main_loop: asyncio.AbstractEventLoop | None = None


def get_connection_manager() -> ConnectionManager:
    return _manager


def get_comms_broker() -> CommsEventBroker:
    global _broker
    if _broker is None:
        _broker = create_comms_broker(settings.redis_url, _manager)
    return _broker


def get_comms_notifier() -> CommunicationsNotifier:
    global _notifier
    if _notifier is None:
        _notifier = CommunicationsNotifier(get_comms_broker())
    return _notifier


def get_main_event_loop() -> asyncio.AbstractEventLoop | None:
    return _main_loop


async def startup_communications() -> None:
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    await get_comms_broker().start()


async def shutdown_communications() -> None:
    await get_comms_broker().stop()
