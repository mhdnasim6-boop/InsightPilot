"""Tests for ReflectionService: the single public entry point. Holds no store
of its own — every reflection is persisted as one MemoryType.REFLECTION
memory via the real MemoryService, so these tests prove that round-trip too.
"""

import pytest

from backend.collaboration.models.collaboration_task import CollaborationTask, SubTask
from backend.execution.state.node_status import NodeStatus
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.memory.store.memory_store import MemoryStore
from backend.observability.context import trace_context
from backend.observability.models.agent_trace import AgentTrace
from backend.observability.models.execution_trace import ExecutionTrace
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.stores.trace_store import TraceStore
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.reflection.exceptions import ReflectionNotFoundError
from backend.reflection.services.reflection_service import ReflectionService
from backend.utils.time import utc_now


def _plan(goal: str = "Analyze sales", plan_id: str = "p1") -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(plan_id=plan_id, goal=goal, status=PlanStatus.READY, created_at=now, updated_at=now)


def _trace(plan_id: str = "p1", agent_status: ExecutionStatus = ExecutionStatus.COMPLETED) -> ExecutionTrace:
    now = utc_now()
    return ExecutionTrace(
        trace_id="t1",
        plan_id=plan_id,
        session_id="sess-1",
        start_time=now,
        end_time=now,
        duration_ms=500.0,
        status=PlanStatus.COMPLETED,
        agent_traces=[
            AgentTrace(
                agent_name="file_agent", start_time=now, end_time=now, duration_ms=500.0, status=agent_status,
                input_size=1, output_size=1,
            )
        ],
    )


def _service() -> ReflectionService:
    return ReflectionService(MemoryService(store=MemoryStore()))


def test_generate_stores_one_reflection_memory() -> None:
    memory_service = MemoryService(store=MemoryStore())
    service = ReflectionService(memory_service)

    result = service.generate(_plan(), _trace())

    memories = memory_service.list_all()
    assert len(memories) == 1
    assert memories[0].memory_type == MemoryType.REFLECTION
    assert memories[0].memory_id == result.reflection_id


def test_generate_produces_a_correct_review() -> None:
    result = _service().generate(_plan(), _trace())
    assert result.review.overall_success is True
    assert result.review.execution_score.value == 100.0
    assert result.plan_id == "p1"
    assert result.trace_id == "t1"
    assert result.session_id == "sess-1"


def test_generate_reflects_agent_failures() -> None:
    result = _service().generate(_plan(), _trace(agent_status=ExecutionStatus.FAILED))
    assert result.review.overall_success is False
    assert any(r.category.value == "retry" for r in result.review.recommendations) or any(
        r.category.value == "tool_choice" for r in result.review.recommendations
    )


def test_get_round_trips_a_generated_reflection() -> None:
    service = _service()
    generated = service.generate(_plan(), _trace())
    fetched = service.get(generated.reflection_id)
    assert fetched.reflection_id == generated.reflection_id
    assert fetched.review.execution_score.value == generated.review.execution_score.value


def test_get_raises_for_unknown_reflection() -> None:
    with pytest.raises(ReflectionNotFoundError):
        _service().get("does-not-exist")


def test_get_raises_for_a_non_reflection_memory_id() -> None:
    memory_service = MemoryService(store=MemoryStore())
    item = memory_service.remember(
        title="Not a reflection", summary="", memory_type=MemoryType.DATASET, content={}
    )
    service = ReflectionService(memory_service)
    with pytest.raises(ReflectionNotFoundError):
        service.get(item.memory_id)


def test_list_all_returns_every_stored_reflection() -> None:
    service = _service()
    service.generate(_plan(plan_id="p1"), _trace(plan_id="p1"))
    service.generate(_plan(plan_id="p2"), _trace(plan_id="p2"))
    reflections = service.list_all()
    assert len(reflections) == 2


def test_statistics_averages_across_reflections() -> None:
    service = _service()
    service.generate(_plan(plan_id="p1"), _trace(plan_id="p1", agent_status=ExecutionStatus.COMPLETED))
    service.generate(_plan(plan_id="p2"), _trace(plan_id="p2", agent_status=ExecutionStatus.FAILED))

    stats = service.statistics()

    assert stats.total_reflections == 2
    assert stats.success_count == 1
    assert stats.average_execution_score == (100.0 + 85.0) / 2


def test_statistics_with_no_reflections() -> None:
    stats = _service().statistics()
    assert stats.total_reflections == 0


def test_export_json_and_markdown() -> None:
    service = _service()
    result = service.generate(_plan(), _trace())
    json_export = service.export(result.reflection_id, "json")
    markdown_export = service.export(result.reflection_id, "markdown")
    assert result.reflection_id in json_export
    assert "Execution Review" in markdown_export


def test_generate_folds_in_collaboration_summary() -> None:
    now = utc_now()
    task = CollaborationTask(
        collaboration_id="c1", goal="test", status=PlanStatus.COMPLETED,
        subtasks={"a": SubTask(subtask_id="a", description="a", assigned_agent="file_agent", status=NodeStatus.COMPLETED)},
        subtask_order=["a"], created_at=now, updated_at=now,
    )
    result = _service().generate(_plan(), _trace(), collaboration_task=task)
    assert result.collaboration_id == "c1"
    assert result.review.collaboration_summary["used_collaboration"] is True


def test_generate_traces_via_observability_service_when_a_trace_is_active() -> None:
    observability_service = ObservabilityService(TraceStore())
    memory_service = MemoryService(store=MemoryStore())
    service = ReflectionService(memory_service, observability_service)
    trace_id = observability_service.start_trace("outer-plan")

    with trace_context(trace_id):
        service.generate(_plan(), _trace())

    trace = observability_service.get_trace(trace_id)
    assert any(t.tool_name == "reflection.generate" for t in trace.tool_traces)
