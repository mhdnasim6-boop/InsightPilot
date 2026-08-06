"""Tests for backend.realtime.websocket: WebSocketConnection and WebSocketManager.

Uses a small fake in place of FastAPI's own ``WebSocket`` (mirrors this
codebase's existing "fake the outermost leaf, keep everything else real"
convention, e.g. ``_SpyTool`` in ``tests/test_agents_use_tools.py``) —
``WebSocketConnection`` only ever calls ``accept``/``send_json``/
``receive_json``/``close`` on it, so a fake exposing exactly those four
methods is a faithful stand-in with no real socket involved.
"""

import asyncio
from typing import Any

from backend.realtime.broker.subscription_manager import SubscriptionManager
from backend.realtime.events.event import Event
from backend.realtime.events.event_envelope import EventEnvelope
from backend.realtime.events.event_type import EventType
from backend.realtime.websocket.websocket_connection import WebSocketConnection
from backend.realtime.websocket.websocket_manager import WebSocketManager


class _FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict[str, Any]] = []
        self.closed_code: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, Any]) -> None:
        self.sent.append(message)

    async def receive_json(self) -> dict[str, Any]:
        raise NotImplementedError

    async def close(self, code: int = 1000) -> None:
        self.closed_code = code


def _envelope(event_type: EventType, **kwargs: object) -> EventEnvelope:
    return EventEnvelope(sequence=1, event=Event(event_type=event_type, **kwargs))  # type: ignore[arg-type]


def test_connection_accept_and_send_envelope() -> None:
    fake = _FakeWebSocket()
    connection = WebSocketConnection(fake)  # type: ignore[arg-type]

    async def scenario() -> None:
        await connection.accept()
        await connection.send_envelope(_envelope(EventType.WORKFLOW_STARTED, workflow_id="w1"))

    asyncio.run(scenario())

    assert fake.accepted
    assert fake.sent[0]["event"]["workflow_id"] == "w1"


def test_connection_has_a_stable_generated_id_by_default() -> None:
    connection = WebSocketConnection(_FakeWebSocket())  # type: ignore[arg-type]
    assert connection.connection_id


def test_manager_connect_registers_and_accepts() -> None:
    manager = WebSocketManager(SubscriptionManager())
    fake = _FakeWebSocket()
    connection = WebSocketConnection(fake, connection_id="c1")  # type: ignore[arg-type]

    asyncio.run(manager.connect(connection))

    assert fake.accepted
    assert manager.connection_count() == 1
    assert manager.get("c1") is connection


def test_manager_disconnect_removes_connection_and_subscription() -> None:
    subscription_manager = SubscriptionManager()
    subscription_manager.subscribe("c1")
    manager = WebSocketManager(subscription_manager)
    connection = WebSocketConnection(_FakeWebSocket(), connection_id="c1")  # type: ignore[arg-type]
    asyncio.run(manager.connect(connection))

    manager.disconnect("c1")

    assert manager.get("c1") is None
    assert not subscription_manager.is_subscribed("c1")


def test_manager_broadcast_only_reaches_matching_subscribers() -> None:
    subscription_manager = SubscriptionManager()
    manager = WebSocketManager(subscription_manager)
    fake_subscribed, fake_unsubscribed = _FakeWebSocket(), _FakeWebSocket()
    subscribed = WebSocketConnection(fake_subscribed, connection_id="subscribed")  # type: ignore[arg-type]
    unsubscribed = WebSocketConnection(fake_unsubscribed, connection_id="unsubscribed")  # type: ignore[arg-type]

    async def scenario() -> None:
        await manager.connect(subscribed)
        await manager.connect(unsubscribed)
        subscription_manager.subscribe("subscribed")
        await manager.broadcast(_envelope(EventType.WORKFLOW_STARTED))

    asyncio.run(scenario())

    assert len(fake_subscribed.sent) == 1
    assert fake_unsubscribed.sent == []


def test_manager_send_to_bypasses_filter() -> None:
    manager = WebSocketManager(SubscriptionManager())
    fake = _FakeWebSocket()
    connection = WebSocketConnection(fake, connection_id="c1")  # type: ignore[arg-type]

    async def scenario() -> None:
        await manager.connect(connection)
        await manager.send_to("c1", _envelope(EventType.WORKFLOW_STARTED))

    asyncio.run(scenario())

    assert len(fake.sent) == 1
