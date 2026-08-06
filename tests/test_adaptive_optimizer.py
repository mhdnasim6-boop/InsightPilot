"""Tests for backend.adaptive.optimizer: the only place plan mutations
happen (planner_optimizer, execution_optimizer), plus advisory-only
approval_optimizer.
"""

from backend.adaptive.models.optimization_result import OptimizationDecisionCategory
from backend.adaptive.models.planning_context import PlanningContext
from backend.adaptive.optimizer.approval_optimizer import generate_approval_decisions
from backend.adaptive.optimizer.execution_optimizer import optimize_execution_order
from backend.adaptive.optimizer.planner_optimizer import optimize_plan_steps
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.utils.time import utc_now


def _plan(steps: list[ExecutionStep]) -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(plan_id="p1", status=PlanStatus.READY, created_at=now, updated_at=now, steps=steps)


def _context(**overrides: dict) -> PlanningContext:
    defaults = {
        "reflection_patterns": {"file_agent_failure_count": 0, "sql_success_count": 0, "browser_skip_count": 0, "approval_delay_count": 0},
        "execution_patterns": {"bottleneck_detected": False, "average_efficiency_score": 100.0, "sample_size": 0, "low_efficiency_count": 0},
        "tool_patterns": {"reused_dataset_count": 0, "reused_report_count": 0, "reused_visualization_count": 0},
    }
    for key, value in overrides.items():
        defaults[key].update(value)  # type: ignore[attr-defined]
    return PlanningContext(**defaults)  # type: ignore[arg-type]


# -- planner_optimizer -------------------------------------------------------------------


def test_optimize_plan_steps_skips_unnecessary_browser_agent() -> None:
    plan = _plan(
        [
            ExecutionStep(step_id="a", name="File", node_name="file_agent"),
            ExecutionStep(step_id="b", name="Browser", node_name="browser_agent"),
        ]
    )
    context = _context(reflection_patterns={"browser_skip_count": 2})

    updated_plan, decisions = optimize_plan_steps(plan, context)

    assert [s.step_id for s in updated_plan.steps] == ["a"]
    assert len(decisions) == 1
    assert decisions[0].category == OptimizationDecisionCategory.SKIP_STEP
    assert decisions[0].applied is True


def test_optimize_plan_steps_does_not_skip_browser_agent_something_depends_on() -> None:
    plan = _plan(
        [
            ExecutionStep(step_id="b", name="Browser", node_name="browser_agent"),
            ExecutionStep(step_id="a", name="File", node_name="file_agent", dependencies=["b"]),
        ]
    )
    context = _context(reflection_patterns={"browser_skip_count": 2})

    updated_plan, decisions = optimize_plan_steps(plan, context)

    assert [s.step_id for s in updated_plan.steps] == ["b", "a"]
    assert decisions == []


def test_optimize_plan_steps_below_threshold_does_not_skip() -> None:
    plan = _plan([ExecutionStep(step_id="b", name="Browser", node_name="browser_agent")])
    context = _context(reflection_patterns={"browser_skip_count": 1})

    updated_plan, decisions = optimize_plan_steps(plan, context)

    assert [s.step_id for s in updated_plan.steps] == ["b"]
    assert decisions == []


def test_optimize_plan_steps_suggests_sql_agent_advisory_only() -> None:
    plan = _plan([ExecutionStep(step_id="a", name="File", node_name="file_agent")])
    context = _context(reflection_patterns={"file_agent_failure_count": 2, "sql_success_count": 2})

    updated_plan, decisions = optimize_plan_steps(plan, context)

    assert updated_plan.steps[0].node_name == "file_agent"  # never mutated
    assert len(decisions) == 1
    assert decisions[0].category == OptimizationDecisionCategory.TOOL_CHOICE
    assert decisions[0].applied is False


def test_optimize_plan_steps_suggests_reusing_artifacts() -> None:
    plan = _plan([ExecutionStep(step_id="a", name="File", node_name="file_agent")])
    context = _context(tool_patterns={"reused_dataset_count": 3, "reused_report_count": 2, "reused_visualization_count": 5})

    _, decisions = optimize_plan_steps(plan, context)

    categories = [d.category for d in decisions]
    assert categories.count(OptimizationDecisionCategory.REUSE_ARTIFACT) == 3
    assert all(not d.applied for d in decisions)


def test_optimize_plan_steps_no_decisions_below_every_threshold() -> None:
    plan = _plan([ExecutionStep(step_id="a", name="File", node_name="file_agent")])
    context = _context()
    updated_plan, decisions = optimize_plan_steps(plan, context)
    assert updated_plan == plan
    assert decisions == []


# -- execution_optimizer -----------------------------------------------------------------


def test_optimize_execution_order_reorders_into_topological_order() -> None:
    plan = _plan(
        [
            ExecutionStep(step_id="b", name="B", node_name="report_agent", dependencies=["a"]),
            ExecutionStep(step_id="a", name="A", node_name="file_agent"),
        ]
    )
    context = _context()

    updated_plan, decisions = optimize_execution_order(plan, context)

    assert [s.step_id for s in updated_plan.steps] == ["a", "b"]
    assert len(decisions) == 1
    assert decisions[0].category == OptimizationDecisionCategory.REORDER
    assert decisions[0].applied is True


def test_optimize_execution_order_no_op_when_already_ordered() -> None:
    plan = _plan(
        [
            ExecutionStep(step_id="a", name="A", node_name="file_agent"),
            ExecutionStep(step_id="b", name="B", node_name="report_agent", dependencies=["a"]),
        ]
    )
    context = _context()

    updated_plan, decisions = optimize_execution_order(plan, context)

    assert updated_plan == plan
    assert decisions == []


def test_optimize_execution_order_flags_repeated_bottleneck() -> None:
    plan = _plan([ExecutionStep(step_id="a", name="A", node_name="file_agent")])
    context = _context(execution_patterns={"bottleneck_detected": True, "average_efficiency_score": 40.0, "sample_size": 3, "low_efficiency_count": 3})

    _, decisions = optimize_execution_order(plan, context)

    assert len(decisions) == 1
    assert decisions[0].category == OptimizationDecisionCategory.PARALLELIZATION
    assert decisions[0].applied is False


# -- approval_optimizer -------------------------------------------------------------------


def test_generate_approval_decisions_below_threshold_returns_nothing() -> None:
    context = _context(reflection_patterns={"approval_delay_count": 1})
    assert generate_approval_decisions(context) == []


def test_generate_approval_decisions_flags_repeated_friction() -> None:
    context = _context(reflection_patterns={"approval_delay_count": 3})
    decisions = generate_approval_decisions(context)
    assert len(decisions) == 1
    assert decisions[0].category == OptimizationDecisionCategory.APPROVAL_REDUCTION
    assert decisions[0].applied is False
    assert decisions[0].evidence_count == 3
