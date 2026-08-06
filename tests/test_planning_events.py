"""Tests for planning events and the PlanEventBus."""

import asyncio

from backend.planning.events.bus import PlanEventBus
from backend.planning.events.events import PlanCompleted, PlanCreated, StepStarted
from backend.utils.time import utc_now


def test_sync_listener_receives_emitted_events() -> None:
    async def scenario() -> None:
        bus = PlanEventBus()
        received: list[object] = []
        bus.subscribe(received.append)

        event = PlanCreated(plan_id="p1", timestamp=utc_now())
        await bus.emit(event)

        assert received == [event]

    asyncio.run(scenario())


def test_async_listener_is_awaited() -> None:
    async def scenario() -> None:
        bus = PlanEventBus()
        received: list[object] = []

        async def async_listener(event: object) -> None:
            await asyncio.sleep(0)
            received.append(event)

        bus.subscribe(async_listener)
        event = StepStarted(plan_id="p1", timestamp=utc_now(), step_id="s1", node_name="planner")
        await bus.emit(event)

        assert received == [event]

    asyncio.run(scenario())


def test_multiple_listeners_all_receive_the_event() -> None:
    async def scenario() -> None:
        bus = PlanEventBus()
        counts = {"a": 0, "b": 0}
        bus.subscribe(lambda _event: counts.__setitem__("a", counts["a"] + 1))
        bus.subscribe(lambda _event: counts.__setitem__("b", counts["b"] + 1))

        await bus.emit(PlanCreated(plan_id="p1", timestamp=utc_now()))

        assert counts == {"a": 1, "b": 1}

    asyncio.run(scenario())


def test_event_field_shapes() -> None:
    completed = PlanCompleted(plan_id="p1", timestamp=utc_now(), status="completed", duration_ms=12.5)
    assert completed.plan_id == "p1"
    assert completed.status == "completed"
    assert completed.duration_ms == 12.5
