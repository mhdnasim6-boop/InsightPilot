"""Tests for backend.realtime.broker: RealtimeEventBus, EventRegistry, SubscriptionManager."""

import asyncio

import pytest

from backend.realtime.broker.event_bus import RealtimeEventBus
from backend.realtime.broker.event_registry import EventRegistry
from backend.realtime.broker.subscription_manager import (
    SubscriptionFilter,
    SubscriptionManager,
)
from backend.realtime.events.event import Event
from backend.realtime.events.event_envelope import EventEnvelope
from backend.realtime.events.event_type import EventType
from backend.realtime.exceptions import UnknownEventTypeError


def _envelope(event_type: EventType, **kwargs: object) -> EventEnvelope:
    return EventEnvelope(sequence=1, event=Event(event_type=event_type, **kwargs))  # type: ignore[arg-type]


# -- RealtimeEventBus ---------------------------------------------------------------


def test_event_bus_emits_to_sync_listener() -> None:
    bus = RealtimeEventBus()
    received: list[EventEnvelope] = []
    bus.subscribe(received.append)

    asyncio.run(bus.emit(_envelope(EventType.WORKFLOW_STARTED)))

    assert len(received) == 1


def test_event_bus_emits_to_async_listener() -> None:
    bus = RealtimeEventBus()
    received: list[EventEnvelope] = []

    async def listener(envelope: EventEnvelope) -> None:
        received.append(envelope)

    async def scenario() -> None:
        bus.subscribe(listener)
        await bus.emit(_envelope(EventType.WORKFLOW_STARTED))

    asyncio.run(scenario())

    assert len(received) == 1


def test_event_bus_unsubscribe_stops_delivery() -> None:
    bus = RealtimeEventBus()
    received: list[EventEnvelope] = []
    bus.subscribe(received.append)
    bus.unsubscribe(received.append)

    asyncio.run(bus.emit(_envelope(EventType.WORKFLOW_STARTED)))

    assert received == []


# -- EventRegistry ------------------------------------------------------------------


def test_event_registry_lists_every_event_type() -> None:
    registry = EventRegistry()
    assert set(registry.list_event_types()) == set(EventType)


def test_event_registry_category_of_known_type() -> None:
    registry = EventRegistry()
    assert registry.category_of(EventType.TOOL_STARTED) == "tool"


def test_event_registry_validate_raises_for_unknown_type() -> None:
    registry = EventRegistry()
    with pytest.raises(UnknownEventTypeError):
        registry.validate("not_a_real_type")  # type: ignore[arg-type]


# -- SubscriptionManager / SubscriptionFilter ---------------------------------------


def test_subscription_filter_with_no_restrictions_matches_everything() -> None:
    subscription_filter = SubscriptionFilter()
    assert subscription_filter.matches(_envelope(EventType.WORKFLOW_STARTED, workflow_id="w1"))


def test_subscription_filter_narrows_by_event_type() -> None:
    subscription_filter = SubscriptionFilter(event_types=frozenset({EventType.TOOL_STARTED}))
    assert not subscription_filter.matches(_envelope(EventType.WORKFLOW_STARTED))
    assert subscription_filter.matches(_envelope(EventType.TOOL_STARTED))


def test_subscription_filter_narrows_by_workflow_id() -> None:
    subscription_filter = SubscriptionFilter(workflow_id="w1")
    assert subscription_filter.matches(_envelope(EventType.WORKFLOW_STARTED, workflow_id="w1"))
    assert not subscription_filter.matches(_envelope(EventType.WORKFLOW_STARTED, workflow_id="w2"))


def test_subscription_manager_matches_only_subscribed_connections() -> None:
    manager = SubscriptionManager()
    manager.subscribe("conn-1", SubscriptionFilter(agent_name="sql_agent"))

    assert manager.matches("conn-1", _envelope(EventType.AGENT_STARTED, agent_name="sql_agent"))
    assert not manager.matches("conn-1", _envelope(EventType.AGENT_STARTED, agent_name="file_agent"))
    assert not manager.matches("conn-unknown", _envelope(EventType.AGENT_STARTED, agent_name="sql_agent"))


def test_subscription_manager_unsubscribe_removes_filter() -> None:
    manager = SubscriptionManager()
    manager.subscribe("conn-1")
    assert manager.is_subscribed("conn-1")

    manager.unsubscribe("conn-1")

    assert not manager.is_subscribed("conn-1")
    assert manager.active_connection_ids() == []
