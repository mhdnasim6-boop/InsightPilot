"""Tests for DefaultPlanOptimizer: topological reordering and metadata dedup."""

from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.planning.optimizer.default import DefaultPlanOptimizer
from backend.utils.time import utc_now


def _step(step_id: str, dependencies: list[str] | None = None) -> ExecutionStep:
    return ExecutionStep(step_id=step_id, name=step_id, node_name="planner", dependencies=dependencies or [])


def _plan(steps: list[ExecutionStep], metadata: dict[str, object] | None = None) -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(plan_id="p1", created_at=now, updated_at=now, steps=steps, metadata=metadata or {})


def test_optimize_reorders_steps_into_dependency_order() -> None:
    # declared out of order: c depends on b depends on a
    plan = _plan([_step("c", dependencies=["b"]), _step("a"), _step("b", dependencies=["a"])])

    optimized = DefaultPlanOptimizer().optimize(plan)

    assert [step.step_id for step in optimized.steps] == ["a", "b", "c"]


def test_optimize_dedupes_list_valued_metadata() -> None:
    plan = _plan([_step("a")], metadata={"tags": ["x", "y", "x", "z"], "owner": "team-a"})

    optimized = DefaultPlanOptimizer().optimize(plan)

    assert optimized.metadata["tags"] == ["x", "y", "z"]
    assert optimized.metadata["owner"] == "team-a"


def test_optimize_does_not_mutate_the_original_plan() -> None:
    plan = _plan([_step("b", dependencies=["a"]), _step("a")], metadata={"tags": ["x", "x"]})

    optimized = DefaultPlanOptimizer().optimize(plan)

    assert [step.step_id for step in plan.steps] == ["b", "a"]
    assert plan.metadata["tags"] == ["x", "x"]
    assert optimized is not plan
