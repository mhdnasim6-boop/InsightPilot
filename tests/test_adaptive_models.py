"""Tests for backend.adaptive.models: shapes, defaults, and immutability."""

from backend.adaptive.models.optimization_result import (
    OptimizationDecision,
    OptimizationDecisionCategory,
    OptimizationResult,
)
from backend.adaptive.models.optimization_statistics import OptimizationStatistics
from backend.adaptive.models.planning_context import PlanningContext
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.utils.time import utc_now


def _plan(plan_id: str = "p1") -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(plan_id=plan_id, status=PlanStatus.READY, created_at=now, updated_at=now)


def test_planning_context_defaults() -> None:
    context = PlanningContext()
    assert context.session_id is None
    assert context.reflection_patterns == {}
    assert context.tool_patterns == {}


def test_optimization_decision_is_frozen() -> None:
    decision = OptimizationDecision(
        decision_id="d1", category=OptimizationDecisionCategory.SKIP_STEP,
        applied=True, message="Skip it.", reason="Unnecessary.",
    )
    try:
        decision.message = "changed"  # type: ignore[misc]
        raised = False
    except Exception:  # noqa: BLE001
        raised = True
    assert raised


def test_optimization_result_defaults() -> None:
    plan = _plan()
    result = OptimizationResult(
        optimization_id="o1", plan_id=plan.plan_id, original_plan=plan, optimized_plan=plan,
        planning_context=PlanningContext(), generated_at=utc_now(),
    )
    assert result.decisions == []
    assert result.execution_savings_estimate_seconds == 0.0
    assert result.approval_savings_estimate == 0
    assert result.parallelism_improved is False


def test_optimization_statistics_defaults() -> None:
    stats = OptimizationStatistics()
    assert stats.total_optimizations == 0
    assert stats.by_category == {}
