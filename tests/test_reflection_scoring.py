"""Tests for backend.reflection.scoring: deterministic 0-100 scores with
transparent breakdowns. No AI, no randomness — every assertion here is
computed from a hand-built ExecutionTrace with known values.
"""

from datetime import timedelta

from backend.observability.models.agent_trace import AgentTrace
from backend.observability.models.execution_trace import ExecutionTrace
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.enums import PlanStatus
from backend.reflection.analyzers.approval_analyzer import analyze_approvals
from backend.reflection.analyzers.execution_analyzer import analyze_execution
from backend.reflection.scoring.confidence_score import compute_confidence_score
from backend.reflection.scoring.efficiency_score import compute_efficiency_score
from backend.reflection.scoring.execution_score import (
    compute_execution_score,
    label_for,
)
from backend.utils.time import utc_now


def _agent_trace(name: str, duration_ms: float, status: ExecutionStatus = ExecutionStatus.COMPLETED) -> AgentTrace:
    now = utc_now()
    return AgentTrace(
        agent_name=name,
        start_time=now - timedelta(milliseconds=duration_ms),
        end_time=now,
        duration_ms=duration_ms,
        status=status,
        input_size=10,
        output_size=10,
    )


def _trace(
    status: PlanStatus = PlanStatus.COMPLETED,
    agent_traces: list[AgentTrace] | None = None,
    duration_ms: float | None = 1000.0,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> ExecutionTrace:
    now = utc_now()
    return ExecutionTrace(
        trace_id="t1",
        plan_id="p1",
        start_time=now,
        end_time=now,
        duration_ms=duration_ms,
        status=status,
        agent_traces=agent_traces or [],
        errors=errors or [],
        warnings=warnings or [],
    )


def test_label_for_boundaries() -> None:
    assert label_for(100.0) == "excellent"
    assert label_for(85.0) == "excellent"
    assert label_for(84.9) == "good"
    assert label_for(65.0) == "good"
    assert label_for(64.9) == "needs_improvement"
    assert label_for(40.0) == "needs_improvement"
    assert label_for(39.9) == "poor"
    assert label_for(0.0) == "poor"


def test_execution_score_perfect_run_is_100() -> None:
    trace = _trace(agent_traces=[_agent_trace("file_agent", 500.0)])
    summary = analyze_execution(trace)
    score = compute_execution_score(trace, summary)
    assert score.value == 100.0
    assert score.label == "excellent"


def test_execution_score_penalizes_failed_agents_and_errors() -> None:
    trace = _trace(
        agent_traces=[_agent_trace("file_agent", 500.0, ExecutionStatus.FAILED)],
        errors=["boom"],
        warnings=["careful"],
    )
    summary = analyze_execution(trace)
    score = compute_execution_score(trace, summary)
    assert score.value == 100.0 - 15.0 - 10.0 - 2.0
    assert score.breakdown["failed_agents_penalty"] == -15.0
    assert score.breakdown["error_penalty"] == -10.0


def test_execution_score_never_goes_below_zero() -> None:
    trace = _trace(
        status=PlanStatus.FAILED,
        agent_traces=[_agent_trace(f"agent_{i}", 100.0, ExecutionStatus.FAILED) for i in range(5)],
        errors=["e"] * 10,
    )
    summary = analyze_execution(trace)
    score = compute_execution_score(trace, summary)
    assert score.value == 0.0


def test_efficiency_score_single_agent_gets_full_credit() -> None:
    trace = _trace(agent_traces=[_agent_trace("file_agent", 500.0)], duration_ms=500.0)
    approvals = analyze_approvals(trace)
    score = compute_efficiency_score(trace, approvals)
    assert score.value == 100.0


def test_efficiency_score_rewards_genuine_parallelism() -> None:
    # Two agents each took 500ms, but the wall-clock trace only took 500ms -> fully parallel.
    trace = _trace(
        agent_traces=[_agent_trace("file_agent", 500.0), _agent_trace("sql_agent", 500.0)], duration_ms=500.0
    )
    approvals = analyze_approvals(trace)
    score = compute_efficiency_score(trace, approvals)
    assert score.value == 100.0


def test_efficiency_score_penalizes_sequential_execution_of_independent_agents() -> None:
    # Two agents each took 500ms, and the wall-clock trace took the full 1000ms -> no parallel gain.
    trace = _trace(
        agent_traces=[_agent_trace("file_agent", 500.0), _agent_trace("sql_agent", 500.0)], duration_ms=1000.0
    )
    approvals = analyze_approvals(trace)
    score = compute_efficiency_score(trace, approvals)
    assert score.value == 50.0


def test_confidence_score_rewards_success_and_memory_reuse() -> None:
    execution_summary = {"overall_success": True, "warning_count": 0, "error_count": 0}
    memory_summary = {"reused_memory": True}
    collaboration_summary = {"used_collaboration": False, "failed_subtasks": 0}
    score = compute_confidence_score(execution_summary, memory_summary, collaboration_summary)
    assert score.value == 90.0


def test_confidence_score_penalizes_failure() -> None:
    execution_summary = {"overall_success": False, "warning_count": 0, "error_count": 0}
    memory_summary = {"reused_memory": False}
    collaboration_summary = {"used_collaboration": False, "failed_subtasks": 0}
    score = compute_confidence_score(execution_summary, memory_summary, collaboration_summary)
    assert score.value == 30.0
