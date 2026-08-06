"""Tests for DependencyResolver: topological ordering (reusing topological_order()),
runnable-node discovery, unreachable-step propagation, and completion detection.
"""

import pytest

from backend.execution.scheduler.dependency_resolver import DependencyResolver
from backend.execution.state.execution_state import ExecutionState, StepExecutionState
from backend.execution.state.node_status import NodeStatus
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.planning.validator.topology import CycleDetectedError
from backend.utils.time import utc_now


def _plan(steps: list[ExecutionStep]) -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(plan_id="p1", status=PlanStatus.READY, created_at=now, updated_at=now, steps=steps)


def _state(plan: ExecutionPlan, overrides: dict[str, NodeStatus] | None = None) -> ExecutionState:
    overrides = overrides or {}
    now = utc_now()
    return ExecutionState(
        execution_id="e1",
        plan_id=plan.plan_id,
        status=PlanStatus.RUNNING,
        steps={
            step.step_id: StepExecutionState(
                step_id=step.step_id, node_name=step.node_name, status=overrides.get(step.step_id, NodeStatus.PENDING)
            )
            for step in plan.steps
        },
        created_at=now,
        updated_at=now,
    )


def _diamond_plan() -> ExecutionPlan:
    return _plan(
        [
            ExecutionStep(step_id="file", name="File", node_name="file_agent"),
            ExecutionStep(step_id="sql", name="SQL", node_name="sql_agent"),
            ExecutionStep(step_id="report", name="Report", node_name="report_agent", dependencies=["file", "sql"]),
        ]
    )


def test_resolver_computes_a_valid_topological_order() -> None:
    resolver = DependencyResolver(_diamond_plan())
    assert resolver.step_order.index("file") < resolver.step_order.index("report")
    assert resolver.step_order.index("sql") < resolver.step_order.index("report")


def test_resolver_raises_cycle_detected_error_for_a_cyclic_plan() -> None:
    plan = _plan(
        [
            ExecutionStep(step_id="a", name="A", node_name="file_agent", dependencies=["b"]),
            ExecutionStep(step_id="b", name="B", node_name="sql_agent", dependencies=["a"]),
        ]
    )
    with pytest.raises(CycleDetectedError):
        DependencyResolver(plan)


def test_dependencies_of_and_dependents_of() -> None:
    resolver = DependencyResolver(_diamond_plan())
    assert set(resolver.dependencies_of("report")) == {"file", "sql"}
    assert resolver.dependents_of("file") == ["report"]
    assert resolver.dependencies_of("file") == []


def test_runnable_steps_returns_independent_steps_with_no_pending_dependencies() -> None:
    plan = _diamond_plan()
    resolver = DependencyResolver(plan)
    state = _state(plan)

    runnable = {step.step_id for step in resolver.runnable_steps(state)}

    assert runnable == {"file", "sql"}


def test_runnable_steps_unlocks_dependent_once_dependencies_complete() -> None:
    plan = _diamond_plan()
    resolver = DependencyResolver(plan)
    state = _state(plan, {"file": NodeStatus.COMPLETED, "sql": NodeStatus.COMPLETED})

    runnable = {step.step_id for step in resolver.runnable_steps(state)}

    assert runnable == {"report"}


def test_runnable_steps_excludes_steps_already_running_or_terminal() -> None:
    plan = _diamond_plan()
    resolver = DependencyResolver(plan)
    state = _state(plan, {"file": NodeStatus.RUNNING, "sql": NodeStatus.FAILED})

    runnable = resolver.runnable_steps(state)

    assert runnable == []


def test_unreachable_steps_propagates_from_a_failed_ancestor() -> None:
    plan = _diamond_plan()
    resolver = DependencyResolver(plan)
    state = _state(plan, {"file": NodeStatus.FAILED})

    assert resolver.unreachable_steps(state) == ["report"]


def test_unreachable_steps_is_empty_when_nothing_has_failed() -> None:
    plan = _diamond_plan()
    resolver = DependencyResolver(plan)
    state = _state(plan)

    assert resolver.unreachable_steps(state) == []


def test_is_finished_true_only_once_every_step_is_terminal() -> None:
    plan = _diamond_plan()
    resolver = DependencyResolver(plan)

    partial = _state(plan, {"file": NodeStatus.COMPLETED, "sql": NodeStatus.COMPLETED})
    assert resolver.is_finished(partial) is False

    complete = _state(
        plan, {"file": NodeStatus.COMPLETED, "sql": NodeStatus.COMPLETED, "report": NodeStatus.COMPLETED}
    )
    assert resolver.is_finished(complete) is True


def test_is_finished_true_when_remaining_steps_are_cancelled_not_completed() -> None:
    plan = _diamond_plan()
    resolver = DependencyResolver(plan)
    state = _state(plan, {"file": NodeStatus.FAILED, "sql": NodeStatus.COMPLETED, "report": NodeStatus.CANCELLED})

    assert resolver.is_finished(state) is True


def test_is_finished_false_while_a_step_is_paused() -> None:
    plan = _diamond_plan()
    resolver = DependencyResolver(plan)
    state = _state(plan, {"file": NodeStatus.COMPLETED, "sql": NodeStatus.PAUSED})

    assert resolver.is_finished(state) is False
