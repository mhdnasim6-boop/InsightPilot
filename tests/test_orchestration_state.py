"""Tests for InsightPilotState and ExecutionStatus."""

from backend.ai.models.responses import TokenUsage
from backend.orchestration.state.state import ExecutionStatus, InsightPilotState
from backend.utils.time import utc_now


def test_state_defaults_are_empty_and_generic() -> None:
    now = utc_now()
    state = InsightPilotState(execution_id="e1", created_at=now, updated_at=now)

    assert state.session_id is None
    assert state.conversation_history == []
    assert state.messages == []
    assert state.artifacts == {}
    assert state.variables == {}
    assert state.metadata == {}
    assert state.errors == []
    assert state.execution_trace == []
    assert state.current_node is None
    assert state.status == ExecutionStatus.PENDING
    assert state.token_usage == TokenUsage()


def test_state_transition_via_model_copy_is_immutable() -> None:
    now = utc_now()
    original = InsightPilotState(execution_id="e1", created_at=now, updated_at=now)
    updated = original.model_copy(update={"current_node": "planner", "execution_trace": ["planner"]})

    assert original.current_node is None
    assert original.execution_trace == []
    assert updated.current_node == "planner"
    assert updated.execution_trace == ["planner"]


def test_execution_status_values() -> None:
    assert {status.value for status in ExecutionStatus} == {
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
        "skipped",
    }
