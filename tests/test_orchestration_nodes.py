"""Tests for the placeholder orchestration nodes."""

import asyncio

from backend.orchestration.nodes.placeholders import EndNode, PlannerNode, RouterNode
from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.utils.time import utc_now


def _initial_state() -> InsightPilotState:
    now = utc_now()
    return InsightPilotState(execution_id="e1", created_at=now, updated_at=now)


def test_planner_node_updates_bookkeeping_only() -> None:
    async def scenario() -> None:
        node = PlannerNode()
        state = _initial_state()

        result = await node.execute(state)

        assert result.current_node == "planner"
        assert result.execution_trace == ["planner"]
        assert result.status == ExecutionStatus.PENDING  # planner does not decide completion

    asyncio.run(scenario())


def test_router_node_appends_to_existing_trace() -> None:
    async def scenario() -> None:
        node = RouterNode()
        state = _initial_state().model_copy(update={"current_node": "planner", "execution_trace": ["planner"]})

        result = await node.execute(state)

        assert result.current_node == "router"
        assert result.execution_trace == ["planner", "router"]

    asyncio.run(scenario())


def test_end_node_marks_execution_completed() -> None:
    async def scenario() -> None:
        node = EndNode()
        state = _initial_state().model_copy(
            update={"current_node": "router", "execution_trace": ["planner", "router"]}
        )

        result = await node.execute(state)

        assert result.current_node == "end"
        assert result.execution_trace == ["planner", "router", "end"]
        assert result.status == ExecutionStatus.COMPLETED

    asyncio.run(scenario())


def test_node_default_validate_and_metadata() -> None:
    node = PlannerNode()
    assert node.validate(_initial_state()) is True
    assert node.metadata() == {"name": "planner"}
