"""Tests for PlanValidator: duplicate ids, missing deps, cycles, unknown nodes, ordering."""

from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.planning.validator.validator import PlanValidator
from backend.utils.time import utc_now


def _step(step_id: str, dependencies: list[str] | None = None, node_name: str = "planner") -> ExecutionStep:
    return ExecutionStep(step_id=step_id, name=step_id, node_name=node_name, dependencies=dependencies or [])


def _plan(steps: list[ExecutionStep]) -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(plan_id="p1", created_at=now, updated_at=now, steps=steps)


def test_valid_plan_passes_and_reports_execution_order() -> None:
    plan = _plan([_step("a"), _step("b", dependencies=["a"]), _step("c", dependencies=["b"])])

    result = PlanValidator().validate(plan)

    assert result.is_valid is True
    assert result.errors == []
    assert result.execution_order == ["a", "b", "c"]


def test_empty_plan_is_valid() -> None:
    result = PlanValidator().validate(_plan([]))
    assert result.is_valid is True
    assert result.execution_order == []


def test_duplicate_step_ids_are_reported() -> None:
    plan = _plan([_step("a"), _step("a")])

    result = PlanValidator().validate(plan)

    assert result.is_valid is False
    assert any(issue.code == "duplicate_step_id" for issue in result.errors)
    assert result.execution_order is None


def test_missing_dependency_is_reported() -> None:
    plan = _plan([_step("a", dependencies=["missing"])])

    result = PlanValidator().validate(plan)

    assert result.is_valid is False
    assert any(issue.code == "missing_dependency" and issue.step_id == "a" for issue in result.errors)
    assert result.execution_order is None


def test_cyclic_dependency_is_reported() -> None:
    plan = _plan([_step("a", dependencies=["b"]), _step("b", dependencies=["a"])])

    result = PlanValidator().validate(plan)

    assert result.is_valid is False
    assert any(issue.code == "cyclic_dependency" for issue in result.errors)
    assert result.execution_order is None


def test_unknown_node_name_is_reported_when_registry_given() -> None:
    plan = _plan([_step("a", node_name="not-a-real-node")])

    result = PlanValidator().validate(plan, known_node_names={"planner", "router", "end"})

    assert result.is_valid is False
    assert any(issue.code == "unknown_node_name" and issue.step_id == "a" for issue in result.errors)


def test_unknown_node_name_is_skipped_without_a_registry() -> None:
    plan = _plan([_step("a", node_name="not-a-real-node")])

    result = PlanValidator().validate(plan, known_node_names=None)

    assert result.is_valid is True


def test_validation_issue_shapes() -> None:
    plan = _plan([_step("a"), _step("a")])
    result = PlanValidator().validate(plan)

    issue = result.errors[0]
    assert issue.severity.value == "error"
    assert isinstance(issue.message, str)
