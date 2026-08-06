"""Tests for MetricsService: aggregate statistics computed over every trace
ObservabilityService knows about — both finalized and still-in-progress.
"""

from datetime import timedelta

from backend.ai.models.responses import TokenUsage
from backend.approval.models.approval import ApprovalStatus, ExecutionApproval
from backend.observability.context import trace_context
from backend.observability.metrics.metrics_service import MetricsService
from backend.observability.models.ai_trace import AICallTrace
from backend.observability.models.tool_trace import ToolTrace
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.stores.trace_store import TraceStore
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.enums import PlanStatus
from backend.utils.time import utc_now


def _agent_result(execution_time: float, status: str = "completed") -> dict:
    return {"step_id": "s1", "status": status, "warnings": [], "execution_time": execution_time, "metadata": {}}


def _tool_trace(tool_name: str, duration_ms: float, status: ExecutionStatus) -> ToolTrace:
    now = utc_now()
    return ToolTrace(tool_name=tool_name, start_time=now, end_time=now, duration_ms=duration_ms, status=status)


def _ai_trace(prompt_tokens: int, completion_tokens: int, latency_ms: float, cost: float) -> AICallTrace:
    now = utc_now()
    return AICallTrace(
        provider="mock",
        model="mock-model",
        tokens=TokenUsage(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=prompt_tokens + completion_tokens
        ),
        start_time=now,
        end_time=now,
        latency_ms=latency_ms,
        estimated_cost=cost,
    )


def test_agent_metrics_aggregates_call_count_and_average_duration_across_traces() -> None:
    service = ObservabilityService(TraceStore())
    metrics = MetricsService(service)

    trace_1 = service.start_trace("plan-1")
    service.record_step(trace_1, "s1", {"sql_agent_result": _agent_result(0.2)}, {})
    service.finalize_trace(trace_1, PlanStatus.COMPLETED)

    trace_2 = service.start_trace("plan-2")
    service.record_step(trace_2, "s1", {"sql_agent_result": _agent_result(0.4, status="failed")}, {})
    service.finalize_trace(trace_2, PlanStatus.FAILED)

    [sql_metrics] = metrics.agent_metrics()
    assert sql_metrics.agent_name == "sql_agent"
    assert sql_metrics.call_count == 2
    assert sql_metrics.completed_count == 1
    assert sql_metrics.failed_count == 1
    assert sql_metrics.total_duration_ms == 600.0
    assert sql_metrics.average_duration_ms == 300.0


def test_tool_metrics_aggregates_across_traces() -> None:
    service = ObservabilityService(TraceStore())
    metrics = MetricsService(service)

    trace_id = service.start_trace("plan-1")
    with trace_context(trace_id):
        service.record_tool_trace(_tool_trace("query_database", 100.0, ExecutionStatus.COMPLETED))
        service.record_tool_trace(_tool_trace("query_database", 300.0, ExecutionStatus.FAILED))
    service.finalize_trace(trace_id, PlanStatus.COMPLETED)

    [tool_metrics] = metrics.tool_metrics()
    assert tool_metrics.tool_name == "query_database"
    assert tool_metrics.call_count == 2
    assert tool_metrics.completed_count == 1
    assert tool_metrics.failed_count == 1
    assert tool_metrics.average_duration_ms == 200.0


def test_ai_metrics_aggregates_tokens_cost_and_latency() -> None:
    service = ObservabilityService(TraceStore())
    metrics = MetricsService(service)

    trace_id = service.start_trace("plan-1")
    with trace_context(trace_id):
        service.record_ai_call(_ai_trace(10, 5, 100.0, 0.01))
        service.record_ai_call(_ai_trace(20, 10, 300.0, 0.02))
    service.finalize_trace(trace_id, PlanStatus.COMPLETED)

    ai_metrics = metrics.ai_metrics()
    assert ai_metrics.call_count == 2
    assert ai_metrics.total_prompt_tokens == 30
    assert ai_metrics.total_completion_tokens == 15
    assert ai_metrics.total_tokens == 45
    assert ai_metrics.total_estimated_cost == 0.03
    assert ai_metrics.average_latency_ms == 200.0


def test_summary_reports_zeros_with_no_traces() -> None:
    metrics = MetricsService(ObservabilityService(TraceStore()))

    summary = metrics.summary()

    assert summary.trace_count == 0
    assert summary.total_execution_time_ms == 0.0
    assert summary.number_of_approvals == 0
    assert summary.average_approval_latency_ms == 0.0


def test_summary_computes_approval_latency_only_over_decided_approvals() -> None:
    service = ObservabilityService(TraceStore())
    metrics = MetricsService(service)

    requested_at = utc_now()
    approved_at = requested_at + timedelta(seconds=2)
    decided = ExecutionApproval(
        approval_id="a1",
        plan_id="plan-1",
        step_id="s1",
        status=ApprovalStatus.APPROVED,
        requested_at=requested_at,
        approved_at=approved_at,
    )
    pending = ExecutionApproval(
        approval_id="a2", plan_id="plan-1", step_id="s2", status=ApprovalStatus.PENDING, requested_at=requested_at
    )

    trace_id = service.start_trace("plan-1")
    service.set_approvals(trace_id, [decided, pending])
    service.finalize_trace(trace_id, PlanStatus.COMPLETED, approval_traces=[decided, pending])

    summary = metrics.summary()

    assert summary.number_of_approvals == 2
    assert summary.average_approval_latency_ms == 2000.0


def test_summary_includes_agent_tool_and_ai_breakdowns() -> None:
    service = ObservabilityService(TraceStore())
    metrics = MetricsService(service)

    trace_id = service.start_trace("plan-1")
    service.record_step(trace_id, "s1", {"sql_agent_result": _agent_result(0.1)}, {})
    with trace_context(trace_id):
        service.record_tool_trace(_tool_trace("query_database", 50.0, ExecutionStatus.COMPLETED))
        service.record_ai_call(_ai_trace(5, 5, 20.0, 0.0))
    service.finalize_trace(trace_id, PlanStatus.COMPLETED)

    summary = metrics.summary()

    assert [a.agent_name for a in summary.agent_metrics] == ["sql_agent"]
    assert [t.tool_name for t in summary.tool_metrics] == ["query_database"]
    assert summary.ai_metrics.call_count == 1
    assert summary.number_of_tool_calls == 1
    assert summary.number_of_ai_calls == 1
