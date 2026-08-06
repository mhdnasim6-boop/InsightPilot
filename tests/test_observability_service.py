"""Tests for ObservabilityService: trace lifecycle, contextvar-based correlation,
and the mutable-accumulator/immutable-snapshot pattern.
"""

import pytest

from backend.ai.models.responses import TokenUsage
from backend.approval.models.approval import ApprovalStatus, ExecutionApproval
from backend.observability.context import trace_context
from backend.observability.exceptions import TraceNotFoundError
from backend.observability.models.ai_trace import AICallTrace
from backend.observability.models.tool_trace import ToolTrace
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.stores.trace_store import TraceStore
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.enums import PlanStatus
from backend.utils.time import utc_now


def _service() -> ObservabilityService:
    return ObservabilityService(TraceStore())


def _sql_result(execution_time: float = 0.5, status: str = "completed", warnings: list[str] | None = None) -> dict:
    return {
        "step_id": "step-1",
        "status": status,
        "warnings": warnings or [],
        "execution_time": execution_time,
        "metadata": {"rows": 3},
    }


def test_start_trace_creates_a_live_running_snapshot() -> None:
    service = _service()
    trace_id = service.start_trace("plan-1", "session-1")

    trace = service.get_trace(trace_id)

    assert trace.trace_id == trace_id
    assert trace.plan_id == "plan-1"
    assert trace.session_id == "session-1"
    assert trace.status == PlanStatus.RUNNING
    assert trace.end_time is None
    assert trace.duration_ms is None
    assert service.trace_id_for_plan("plan-1") == trace_id


def test_get_trace_raises_for_unknown_trace_id() -> None:
    service = _service()
    with pytest.raises(TraceNotFoundError):
        service.get_trace("does-not-exist")


def test_get_trace_for_plan_raises_when_plan_never_started_a_trace() -> None:
    service = _service()
    with pytest.raises(TraceNotFoundError):
        service.get_trace_for_plan("no-such-plan")


def test_mark_status_updates_the_live_snapshot() -> None:
    service = _service()
    trace_id = service.start_trace("plan-1")

    service.mark_status(trace_id, PlanStatus.PAUSED)

    assert service.get_trace(trace_id).status == PlanStatus.PAUSED


def test_record_step_builds_one_agent_trace_per_result_artifact() -> None:
    service = _service()
    trace_id = service.start_trace("plan-1")

    service.record_step(
        trace_id, "step-1", artifacts={"sql_agent_result": _sql_result()}, variables={"query": "select 1"}
    )

    trace = service.get_trace(trace_id)
    assert len(trace.agent_traces) == 1
    agent_trace = trace.agent_traces[0]
    assert agent_trace.agent_name == "sql_agent"
    assert agent_trace.status == ExecutionStatus.COMPLETED
    assert agent_trace.duration_ms == 500.0
    assert agent_trace.metadata == {"rows": 3}


def test_record_step_ignores_non_result_and_non_dict_artifacts() -> None:
    service = _service()
    trace_id = service.start_trace("plan-1")

    service.record_step(
        trace_id,
        "step-1",
        artifacts={"sql_agent_result": _sql_result(), "some_other_key": "value", "plain_list_result": [1, 2]},
        variables={},
    )

    trace = service.get_trace(trace_id)
    assert [a.agent_name for a in trace.agent_traces] == ["sql_agent"]


def test_record_step_deduplicates_per_step_and_agent() -> None:
    service = _service()
    trace_id = service.start_trace("plan-1")
    artifacts = {"sql_agent_result": _sql_result()}

    service.record_step(trace_id, "step-1", artifacts, {})
    service.record_step(trace_id, "step-1", artifacts, {})  # simulates a pause/resume re-settle

    assert len(service.get_trace(trace_id).agent_traces) == 1


def test_record_step_records_the_same_agent_again_for_a_different_step() -> None:
    service = _service()
    trace_id = service.start_trace("plan-1")
    artifacts = {"sql_agent_result": _sql_result()}

    service.record_step(trace_id, "step-1", artifacts, {})
    service.record_step(trace_id, "step-2", artifacts, {})

    assert len(service.get_trace(trace_id).agent_traces) == 2


def test_record_step_is_a_no_op_for_none_or_unknown_trace_id() -> None:
    service = _service()
    service.record_step(None, "step-1", {"sql_agent_result": _sql_result()}, {})
    service.record_step("unknown", "step-1", {"sql_agent_result": _sql_result()}, {})
    # Nothing raised, nothing to assert on — there's no trace to have recorded into.


def test_record_tool_trace_uses_current_trace_id_contextvar() -> None:
    service = _service()
    trace_id = service.start_trace("plan-1")
    now = utc_now()
    tool_trace = ToolTrace(
        tool_name="query_database", start_time=now, end_time=now, duration_ms=1.0, status=ExecutionStatus.COMPLETED
    )

    with trace_context(trace_id):
        service.record_tool_trace(tool_trace)

    assert service.get_trace(trace_id).tool_traces == [tool_trace]


def test_record_tool_trace_is_a_no_op_outside_a_trace_context() -> None:
    service = _service()
    service.start_trace("plan-1")
    now = utc_now()
    tool_trace = ToolTrace(
        tool_name="query_database", start_time=now, end_time=now, duration_ms=1.0, status=ExecutionStatus.COMPLETED
    )

    service.record_tool_trace(tool_trace)  # no trace_context set — must not raise, must not attach anywhere

    assert all(t.tool_traces == [] for t in service.list_traces())


def test_record_ai_call_uses_current_trace_id_contextvar() -> None:
    service = _service()
    trace_id = service.start_trace("plan-1")
    now = utc_now()
    ai_trace = AICallTrace(
        provider="mock",
        model="mock-model",
        tokens=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        start_time=now,
        end_time=now,
        latency_ms=1.0,
        estimated_cost=0.0,
    )

    with trace_context(trace_id):
        service.record_ai_call(ai_trace)

    assert service.get_trace(trace_id).ai_calls == [ai_trace]


def test_set_approvals_replaces_the_live_snapshots_approval_list() -> None:
    service = _service()
    trace_id = service.start_trace("plan-1")
    approval = ExecutionApproval(
        approval_id="a1", plan_id="plan-1", step_id="step-1", status=ApprovalStatus.PENDING, requested_at=utc_now()
    )

    service.set_approvals(trace_id, [approval])

    assert service.get_trace(trace_id).approval_traces == [approval]


def test_finalize_trace_freezes_and_stores_the_trace() -> None:
    service = _service()
    trace_id = service.start_trace("plan-1")
    service.record_step(trace_id, "step-1", {"sql_agent_result": _sql_result()}, {})

    finalized = service.finalize_trace(trace_id, PlanStatus.COMPLETED)

    assert finalized.status == PlanStatus.COMPLETED
    assert finalized.end_time is not None
    assert finalized.duration_ms is not None
    assert len(finalized.agent_traces) == 1
    # It's gone from "in progress" — a second finalize must fail.
    with pytest.raises(TraceNotFoundError):
        service.finalize_trace(trace_id, PlanStatus.COMPLETED)


def test_get_trace_returns_the_finalized_trace_after_finalize() -> None:
    service = _service()
    trace_id = service.start_trace("plan-1")

    service.finalize_trace(trace_id, PlanStatus.FAILED)

    assert service.get_trace(trace_id).status == PlanStatus.FAILED
    assert service.get_trace_for_plan("plan-1").status == PlanStatus.FAILED


def test_record_error_attaches_to_the_finalized_trace() -> None:
    service = _service()
    trace_id = service.start_trace("plan-1")

    service.record_error(trace_id, "boom")
    finalized = service.finalize_trace(trace_id, PlanStatus.FAILED)

    assert finalized.errors == ["boom"]


def test_list_traces_returns_in_progress_before_finalized() -> None:
    service = _service()
    finalized_trace_id = service.start_trace("plan-1")
    service.finalize_trace(finalized_trace_id, PlanStatus.COMPLETED)
    live_trace_id = service.start_trace("plan-2")

    traces = service.list_traces()

    assert traces[0].trace_id == live_trace_id
    assert traces[0].status == PlanStatus.RUNNING
    assert traces[1].trace_id == finalized_trace_id
    assert traces[1].status == PlanStatus.COMPLETED
