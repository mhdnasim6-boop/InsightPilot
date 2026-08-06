"""Tests for the observability trace models: frozen (immutable) construction,
and that ExecutionTrace correctly reuses ExecutionApproval/PlanStatus.
"""

import pytest
from pydantic import ValidationError

from backend.ai.models.responses import TokenUsage
from backend.approval.models.approval import ApprovalStatus, ExecutionApproval
from backend.observability.models.agent_trace import AgentTrace
from backend.observability.models.ai_trace import AICallTrace
from backend.observability.models.execution_trace import ExecutionTrace
from backend.observability.models.tool_trace import ToolTrace
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.enums import PlanStatus
from backend.utils.time import utc_now


def _agent_trace() -> AgentTrace:
    now = utc_now()
    return AgentTrace(
        agent_name="sql_agent",
        start_time=now,
        end_time=now,
        duration_ms=12.5,
        status=ExecutionStatus.COMPLETED,
        input_size=10,
        output_size=20,
    )


def test_agent_trace_is_frozen() -> None:
    trace = _agent_trace()
    with pytest.raises(ValidationError):
        trace.agent_name = "other_agent"  # type: ignore[misc]


def test_tool_trace_is_frozen_and_defaults_agent_name_to_none() -> None:
    now = utc_now()
    trace = ToolTrace(
        tool_name="query_database",
        start_time=now,
        end_time=now,
        duration_ms=5.0,
        status=ExecutionStatus.COMPLETED,
    )
    assert trace.agent_name is None
    with pytest.raises(ValidationError):
        trace.tool_name = "other_tool"  # type: ignore[misc]


def test_ai_call_trace_reuses_token_usage() -> None:
    now = utc_now()
    usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    trace = AICallTrace(
        provider="mock",
        model="mock-model",
        tokens=usage,
        start_time=now,
        end_time=now,
        latency_ms=42.0,
        estimated_cost=0.0,
        temperature=0.7,
    )
    assert trace.tokens is usage
    assert trace.tokens.total_tokens == 15


def test_execution_trace_is_frozen_and_reuses_plan_status_and_execution_approval() -> None:
    now = utc_now()
    approval = ExecutionApproval(
        approval_id="a1", plan_id="p1", step_id="s1", status=ApprovalStatus.APPROVED, requested_at=now
    )
    trace = ExecutionTrace(
        trace_id="t1",
        plan_id="p1",
        start_time=now,
        end_time=now,
        duration_ms=100.0,
        status=PlanStatus.COMPLETED,
        agent_traces=[_agent_trace()],
        approval_traces=[approval],
    )
    assert trace.status is PlanStatus.COMPLETED
    assert trace.approval_traces[0] is approval
    with pytest.raises(ValidationError):
        trace.status = PlanStatus.FAILED  # type: ignore[misc]


def test_execution_trace_defaults_to_empty_collections_and_no_end_time() -> None:
    trace = ExecutionTrace(trace_id="t2", plan_id="p2", start_time=utc_now(), status=PlanStatus.RUNNING)
    assert trace.end_time is None
    assert trace.duration_ms is None
    assert trace.agent_traces == []
    assert trace.tool_traces == []
    assert trace.ai_calls == []
    assert trace.approval_traces == []
    assert trace.errors == []
    assert trace.warnings == []
