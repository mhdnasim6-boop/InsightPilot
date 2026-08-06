"""Tests for orchestration events and the EventBus."""

import asyncio

from backend.orchestration.events.bus import EventBus
from backend.orchestration.events.events import (
    ExecutionCompleted,
    ExecutionStarted,
    NodeStarted,
)
from backend.utils.time import utc_now


def test_sync_listener_receives_emitted_events() -> None:
    async def scenario() -> None:
        bus = EventBus()
        received: list[object] = []
        bus.subscribe(received.append)

        event = ExecutionStarted(execution_id="e1", timestamp=utc_now())
        await bus.emit(event)

        assert received == [event]

    asyncio.run(scenario())


def test_async_listener_is_awaited() -> None:
    async def scenario() -> None:
        bus = EventBus()
        received: list[object] = []

        async def async_listener(event: object) -> None:
            await asyncio.sleep(0)
            received.append(event)

        bus.subscribe(async_listener)
        event = NodeStarted(execution_id="e1", timestamp=utc_now(), node_name="planner")
        await bus.emit(event)

        assert received == [event]

    asyncio.run(scenario())


def test_multiple_listeners_all_receive_the_event() -> None:
    async def scenario() -> None:
        bus = EventBus()
        counts = {"a": 0, "b": 0}
        bus.subscribe(lambda _event: counts.__setitem__("a", counts["a"] + 1))
        bus.subscribe(lambda _event: counts.__setitem__("b", counts["b"] + 1))

        await bus.emit(ExecutionStarted(execution_id="e1", timestamp=utc_now()))

        assert counts == {"a": 1, "b": 1}

    asyncio.run(scenario())


def test_event_field_shapes() -> None:
    completed = ExecutionCompleted(execution_id="e1", timestamp=utc_now(), status="completed", duration_ms=12.5)
    assert completed.execution_id == "e1"
    assert completed.status == "completed"
    assert completed.duration_ms == 12.5
