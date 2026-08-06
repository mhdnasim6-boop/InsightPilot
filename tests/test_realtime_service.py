"""Tests for backend.realtime.services.realtime_service.RealtimeService — the
one public API of the realtime layer: publish, replay, and WebSocket lifecycle.
"""

import asyncio
from typing import Any

from backend.realtime.broker.event_bus import RealtimeEventBus
from backend.realtime.broker.event_registry import EventRegistry
from backend.realtime.broker.subscription_manager import (
    SubscriptionFilter,
    SubscriptionManager,
)
from backend.realtime.events.event import Event
from backend.realtime.events.event_type import EventType
from backend.realtime.replay.replay_buffer import ReplayBuffer
from backend.realtime.replay.replay_service import ReplayService
from backend.realtime.services.realtime_service import RealtimeService
from backend.realtime.websocket.websocket_connection import WebSocketConnection
from backend.realtime.websocket.websocket_manager import WebSocketManager


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def accept(self) -> None:
        pass

    async def send_json(self, message: dict[str, Any]) -> None:
        self.sent.append(message)

    async def receive_json(self) -> dict[str, Any]:
        raise NotImplementedError

    async def close(self, code: int = 1000) -> None:
        pass


def _build_service() -> RealtimeService:
    subscription_manager = SubscriptionManager()
    replay_buffer = ReplayBuffer()
    return RealtimeService(
        event_bus=RealtimeEventBus(),
        replay_buffer=replay_buffer,
        replay_service=ReplayService(replay_buffer),
        subscription_manager=subscription_manager,
        websocket_manager=WebSocketManager(subscription_manager),
        event_registry=EventRegistry(),
    )


def test_publish_records_into_replay_buffer_even_with_no_running_loop() -> None:
    service = _build_service()

    envelope = service.publish(Event(event_type=EventType.WORKFLOW_STARTED, workflow_id="w1"))

    assert envelope.sequence == 1
    assert service.replay() == [envelope]


def test_publish_async_broadcasts_to_subscribed_connection() -> None:
    service = _build_service()
    fake = _FakeWebSocket()
    connection = WebSocketConnection(fake, connection_id="c1")  # type: ignore[arg-type]

    async def scenario() -> None:
        await service.connect(connection)
        service.subscribe("c1")
        await service.publish_async(Event(event_type=EventType.WORKFLOW_STARTED, workflow_id="w1"))

    asyncio.run(scenario())

    assert len(fake.sent) == 1
    assert fake.sent[0]["event"]["workflow_id"] == "w1"


def test_publish_async_does_not_broadcast_to_unsubscribed_connection() -> None:
    service = _build_service()
    fake = _FakeWebSocket()
    connection = WebSocketConnection(fake, connection_id="c1")  # type: ignore[arg-type]

    async def scenario() -> None:
        await service.connect(connection)
        await service.publish_async(Event(event_type=EventType.WORKFLOW_STARTED))

    asyncio.run(scenario())

    assert fake.sent == []


def test_list_event_types_returns_all_24() -> None:
    service = _build_service()
    assert len(service.list_event_types()) == 24


def test_list_subscriptions_reflects_active_filters() -> None:
    service = _build_service()
    service.subscribe("c1")
    service.subscribe("c2", SubscriptionFilter(agent_name="sql_agent"))

    assert set(service.list_subscriptions()) == {"c1", "c2"}

    service.unsubscribe("c1")
    assert service.list_subscriptions() == ["c2"]


def test_disconnect_clears_subscription() -> None:
    service = _build_service()
    connection = WebSocketConnection(_FakeWebSocket(), connection_id="c1")  # type: ignore[arg-type]

    async def scenario() -> None:
        await service.connect(connection)
        service.subscribe("c1")

    asyncio.run(scenario())
    service.disconnect("c1")

    assert service.list_subscriptions() == []


def test_replay_to_sends_matching_history_directly_to_one_connection() -> None:
    service = _build_service()
    service.publish(Event(event_type=EventType.WORKFLOW_STARTED, workflow_id="w1"))
    service.publish(Event(event_type=EventType.TOOL_STARTED))
    fake = _FakeWebSocket()
    connection = WebSocketConnection(fake, connection_id="c1")  # type: ignore[arg-type]

    async def scenario() -> list[Any]:
        await service.connect(connection)
        service.subscribe("c1", SubscriptionFilter(workflow_id="w1"))
        return await service.replay_to("c1", count=10)

    replayed = asyncio.run(scenario())

    assert len(replayed) == 1
    assert len(fake.sent) == 1
    assert fake.sent[0]["event"]["workflow_id"] == "w1"
