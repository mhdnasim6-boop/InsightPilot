"""Tests for AdaptivePlanningService: the single public entry point. Holds no
store of its own — every optimization is persisted as one
MemoryType.ADAPTIVE_PLAN memory via the real MemoryService, so these tests
prove that round-trip too.
"""

import pytest

from backend.adaptive.exceptions import OptimizationNotFoundError
from backend.adaptive.services.adaptive_planning_service import AdaptivePlanningService
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.memory.store.memory_store import MemoryStore
from backend.observability.context import trace_context
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.stores.trace_store import TraceStore
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.reflection.services.reflection_service import ReflectionService
from backend.utils.time import utc_now


def _plan(plan_id: str = "p1", goal: str = "Analyze sales") -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(
        plan_id=plan_id, goal=goal, status=PlanStatus.READY, created_at=now, updated_at=now,
        steps=[ExecutionStep(step_id="a", name="A", node_name="file_agent")],
    )


def _service() -> AdaptivePlanningService:
    memory_service = MemoryService(store=MemoryStore())
    return AdaptivePlanningService(memory_service, ReflectionService(memory_service))


def test_explain_does_not_store_anything() -> None:
    memory_service = MemoryService(store=MemoryStore())
    service = AdaptivePlanningService(memory_service, ReflectionService(memory_service))

    result = service.explain(_plan())

    assert result.optimization_id == ""
    assert memory_service.list_all() == []


def test_optimize_stores_one_adaptive_plan_memory() -> None:
    memory_service = MemoryService(store=MemoryStore())
    service = AdaptivePlanningService(memory_service, ReflectionService(memory_service))

    result = service.optimize(_plan())

    memories = memory_service.list_all()
    assert len(memories) == 1
    assert memories[0].memory_type == MemoryType.ADAPTIVE_PLAN
    assert memories[0].memory_id == result.optimization_id


def test_optimize_with_no_history_produces_no_decisions() -> None:
    result = _service().optimize(_plan())
    assert result.decisions == []
    assert result.optimized_plan == result.original_plan


def test_history_returns_every_stored_optimization() -> None:
    service = _service()
    service.optimize(_plan(plan_id="p1"))
    service.optimize(_plan(plan_id="p2"))
    assert len(service.history()) == 2


def test_statistics_with_no_optimizations() -> None:
    stats = _service().statistics()
    assert stats.total_optimizations == 0


def test_statistics_aggregates_decisions() -> None:
    service = _service()
    service.optimize(_plan(plan_id="p1"))
    service.optimize(_plan(plan_id="p2"))
    stats = service.statistics()
    assert stats.total_optimizations == 2


def test_export_json_and_markdown() -> None:
    service = _service()
    result = service.optimize(_plan())
    json_export = service.export(result.optimization_id, "json")
    markdown_export = service.export(result.optimization_id, "markdown")
    assert result.optimization_id in json_export
    assert "Plan Optimization" in markdown_export


def test_export_raises_for_unknown_optimization() -> None:
    with pytest.raises(OptimizationNotFoundError):
        _service().export("does-not-exist", "json")


def test_export_raises_for_a_non_optimization_memory_id() -> None:
    memory_service = MemoryService(store=MemoryStore())
    item = memory_service.remember(title="Not an optimization", summary="", memory_type=MemoryType.DATASET, content={})
    service = AdaptivePlanningService(memory_service, ReflectionService(memory_service))
    with pytest.raises(OptimizationNotFoundError):
        service.export(item.memory_id, "json")


def test_optimize_traces_via_observability_service_when_a_trace_is_active() -> None:
    observability_service = ObservabilityService(TraceStore())
    memory_service = MemoryService(store=MemoryStore())
    service = AdaptivePlanningService(memory_service, ReflectionService(memory_service), observability_service)
    trace_id = observability_service.start_trace("outer-plan")

    with trace_context(trace_id):
        service.optimize(_plan())

    trace = observability_service.get_trace(trace_id)
    assert any(t.tool_name == "adaptive.optimize" for t in trace.tool_traces)
