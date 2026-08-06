"""Tests for backend.reflection.analyzers: execution, tool usage, approval,
memory, and collaboration — each a pure function over already-existing
models, no AI, no network.
"""

from datetime import timedelta

from backend.approval.models.approval import ApprovalStatus, ExecutionApproval
from backend.collaboration.models.collaboration_task import CollaborationTask, SubTask
from backend.execution.state.node_status import NodeStatus
from backend.memory.models.memory_query import MemoryQuery
from backend.memory.models.memory_result import MemoryResult
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.observability.models.agent_trace import AgentTrace
from backend.observability.models.execution_trace import ExecutionTrace
from backend.observability.models.tool_trace import ToolTrace
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.reflection.analyzers.approval_analyzer import analyze_approvals
from backend.reflection.analyzers.collaboration_analyzer import analyze_collaboration
from backend.reflection.analyzers.execution_analyzer import (
    analyze_execution,
    derive_strengths_and_weaknesses,
)
from backend.reflection.analyzers.memory_analyzer import analyze_memory
from backend.reflection.analyzers.tool_usage_analyzer import analyze_tool_usage
from backend.reflection.scoring.confidence_score import ConfidenceScore
from backend.reflection.scoring.efficiency_score import EfficiencyScore
from backend.utils.time import utc_now


def _agent_trace(name: str, status: ExecutionStatus = ExecutionStatus.COMPLETED, duration_ms: float = 100.0) -> AgentTrace:
    now = utc_now()
    return AgentTrace(
        agent_name=name, start_time=now, end_time=now, duration_ms=duration_ms, status=status, input_size=1, output_size=1
    )


def _tool_trace(name: str, status: ExecutionStatus = ExecutionStatus.COMPLETED, duration_ms: float = 50.0) -> ToolTrace:
    now = utc_now()
    return ToolTrace(tool_name=name, start_time=now, end_time=now, duration_ms=duration_ms, status=status)


def _trace(**overrides: object) -> ExecutionTrace:
    now = utc_now()
    defaults = {
        "trace_id": "t1", "plan_id": "p1", "start_time": now, "end_time": now, "duration_ms": 100.0,
        "status": PlanStatus.COMPLETED,
    }
    defaults.update(overrides)
    return ExecutionTrace(**defaults)  # type: ignore[arg-type]


# -- execution_analyzer --------------------------------------------------------------


def test_analyze_execution_reports_success_when_completed_with_no_failures() -> None:
    trace = _trace(agent_traces=[_agent_trace("file_agent")])
    summary = analyze_execution(trace)
    assert summary["overall_success"] is True
    assert summary["failed_agents"] == []
    assert summary["completed_agents"] == ["file_agent"]


def test_analyze_execution_reports_failure_when_an_agent_failed_even_if_plan_completed() -> None:
    trace = _trace(agent_traces=[_agent_trace("file_agent", ExecutionStatus.FAILED)])
    summary = analyze_execution(trace)
    assert summary["overall_success"] is False
    assert summary["failed_agents"] == ["file_agent"]


def test_analyze_execution_flags_slow_agents() -> None:
    trace = _trace(agent_traces=[_agent_trace("browser_agent", duration_ms=6000.0)])
    summary = analyze_execution(trace)
    assert summary["slow_agents"] == ["browser_agent"]


def test_derive_strengths_and_weaknesses_reflects_failures_and_slowness() -> None:
    execution_summary = {
        "overall_success": False,
        "agent_count": 1,
        "completed_agents": [],
        "failed_agents": ["file_agent"],
        "slow_agents": ["file_agent"],
    }
    tool_summary = {"failed_tools": ["ingest_dataset"], "total_calls": 1, "calls_per_tool": {}}
    approval_summary = {"rejected_count": 0, "total_approvals": 0}
    efficiency_score = EfficiencyScore(value=40.0, breakdown={}, label="needs_improvement")
    confidence_score = ConfidenceScore(value=30.0, breakdown={}, label="poor")

    strengths, weaknesses = derive_strengths_and_weaknesses(
        execution_summary, tool_summary, approval_summary, efficiency_score, confidence_score
    )

    assert "Execution did not reach a successful, completed status." in weaknesses
    assert any("file_agent" in w for w in weaknesses)
    assert any("ingest_dataset" in w for w in weaknesses)
    assert any("confidence" in w.lower() for w in weaknesses)
    assert strengths == []


def test_derive_strengths_does_not_claim_parallelism_for_a_single_agent() -> None:
    execution_summary = {
        "overall_success": True,
        "agent_count": 1,
        "completed_agents": ["file_agent"],
        "failed_agents": [],
        "slow_agents": [],
    }
    tool_summary = {"failed_tools": [], "total_calls": 0, "calls_per_tool": {}}
    approval_summary = {"rejected_count": 0, "total_approvals": 0}
    efficiency_score = EfficiencyScore(value=100.0, breakdown={}, label="excellent")
    confidence_score = ConfidenceScore(value=90.0, breakdown={}, label="excellent")

    strengths, _ = derive_strengths_and_weaknesses(
        execution_summary, tool_summary, approval_summary, efficiency_score, confidence_score
    )

    assert not any("parallel" in s.lower() for s in strengths)


# -- tool_usage_analyzer -------------------------------------------------------------


def test_analyze_tool_usage_counts_calls_and_failures() -> None:
    trace = _trace(
        tool_traces=[
            _tool_trace("ingest_dataset", duration_ms=10.0),
            _tool_trace("ingest_dataset", duration_ms=20.0),
            _tool_trace("clean_dataset", ExecutionStatus.FAILED, duration_ms=5.0),
        ]
    )
    summary = analyze_tool_usage(trace)
    assert summary["total_calls"] == 3
    assert summary["calls_per_tool"] == {"ingest_dataset": 2, "clean_dataset": 1}
    assert summary["failed_tools"] == ["clean_dataset"]
    assert summary["slowest_tool"] == "ingest_dataset"


def test_analyze_tool_usage_handles_no_calls() -> None:
    summary = analyze_tool_usage(_trace())
    assert summary["total_calls"] == 0
    assert summary["slowest_tool"] is None


# -- approval_analyzer ----------------------------------------------------------------


def test_analyze_approvals_computes_average_delay() -> None:
    requested = utc_now()
    approval = ExecutionApproval(
        approval_id="a1",
        plan_id="p1",
        step_id="s1",
        status=ApprovalStatus.APPROVED,
        requested_at=requested,
        approved_at=requested + timedelta(seconds=30),
    )
    trace = _trace(approval_traces=[approval])
    summary = analyze_approvals(trace)
    assert summary["total_approvals"] == 1
    assert summary["approved_count"] == 1
    assert summary["average_delay_seconds"] == 30.0


def test_analyze_approvals_handles_no_approvals() -> None:
    summary = analyze_approvals(_trace())
    assert summary["total_approvals"] == 0
    assert summary["average_delay_seconds"] == 0.0


# -- memory_analyzer -------------------------------------------------------------------


class _StubMemoryService:
    def __init__(self, items: list) -> None:  # type: ignore[type-arg]
        self._items = items

    def search(self, query: MemoryQuery) -> MemoryResult:
        return MemoryResult(items=self._items, total_matched=len(self._items), query=query)


def test_analyze_memory_excludes_the_current_plan_own_memories() -> None:
    from backend.memory.models.memory_item import MemoryItem

    now = utc_now()
    own_memory = MemoryItem(
        memory_id="m1", title="This plan", summary="", memory_type=MemoryType.DECISION, scope=MemoryScope.SESSION,
        created_at=now, updated_at=now, content={"plan_id": "p1"},
    )
    prior_memory = MemoryItem(
        memory_id="m2", title="A prior plan", summary="", memory_type=MemoryType.DECISION, scope=MemoryScope.SESSION,
        created_at=now, updated_at=now, content={"plan_id": "p0"},
    )
    memory_service = _StubMemoryService([own_memory, prior_memory])
    plan = ExecutionPlan(plan_id="p1", goal="Analyze sales", status=PlanStatus.READY, created_at=now, updated_at=now)

    summary = analyze_memory(memory_service, plan)  # type: ignore[arg-type]

    assert summary["relevant_prior_count"] == 1
    assert summary["relevant_titles"] == ["A prior plan"]
    assert summary["reused_memory"] is True


def test_analyze_memory_with_no_memory_service() -> None:
    now = utc_now()
    plan = ExecutionPlan(plan_id="p1", goal="Analyze sales", status=PlanStatus.READY, created_at=now, updated_at=now)
    summary = analyze_memory(None, plan)
    assert summary["reused_memory"] is False


# -- collaboration_analyzer -------------------------------------------------------------


def test_analyze_collaboration_with_no_session() -> None:
    summary = analyze_collaboration(None)
    assert summary["used_collaboration"] is False


def test_analyze_collaboration_counts_subtask_outcomes() -> None:
    now = utc_now()
    task = CollaborationTask(
        collaboration_id="c1",
        goal="test",
        status=PlanStatus.COMPLETED,
        subtasks={
            "a": SubTask(subtask_id="a", description="a", assigned_agent="file_agent", status=NodeStatus.COMPLETED),
            "b": SubTask(subtask_id="b", description="b", assigned_agent="report_agent", status=NodeStatus.FAILED),
        },
        subtask_order=["a", "b"],
        created_at=now,
        updated_at=now,
    )
    summary = analyze_collaboration(task)
    assert summary["used_collaboration"] is True
    assert summary["subtask_count"] == 2
    assert summary["completed_subtasks"] == 1
    assert summary["failed_subtasks"] == 1
