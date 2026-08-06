"""Tests for PlannerPlanValidator: structural reuse of PlanValidator + confidence handling."""

from backend.agents.planner.validation.plan_validator import PlannerPlanValidator
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.utils.time import utc_now


def _plan(steps: list[ExecutionStep]) -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(plan_id="p1", created_at=now, updated_at=now, steps=steps)


def _step(step_id: str, node_name: str, dependencies: list[str] | None = None) -> ExecutionStep:
    return ExecutionStep(step_id=step_id, name=step_id, node_name=node_name, dependencies=dependencies or [])


def test_valid_plan_with_known_services_and_high_confidence_passes() -> None:
    plan = _plan([_step("s1", "ingestion"), _step("s2", "cleaning", ["s1"])])

    result = PlannerPlanValidator().validate(plan, {"ingestion", "cleaning"}, confidence=0.9)

    assert result.is_valid is True
    assert result.errors == []
    assert result.warnings == []


def test_unknown_node_name_fails_validation() -> None:
    plan = _plan([_step("s1", "ingestion"), _step("s2", "analysis", ["s1"])])

    result = PlannerPlanValidator().validate(plan, {"ingestion", "cleaning"}, confidence=0.9)

    assert result.is_valid is False
    assert any(issue.code == "unknown_node_name" for issue in result.errors)


def test_cyclic_dependency_fails_validation() -> None:
    plan = _plan([_step("s1", "ingestion", ["s2"]), _step("s2", "cleaning", ["s1"])])

    result = PlannerPlanValidator().validate(plan, {"ingestion", "cleaning"}, confidence=0.9)

    assert result.is_valid is False
    assert any(issue.code == "cyclic_dependency" for issue in result.errors)


def test_low_confidence_adds_a_warning_without_invalidating() -> None:
    plan = _plan([_step("s1", "ingestion")])

    result = PlannerPlanValidator(confidence_threshold=0.8).validate(plan, {"ingestion"}, confidence=0.4)

    assert result.is_valid is True
    assert any(issue.code == "low_confidence" for issue in result.warnings)


def test_high_confidence_does_not_add_a_low_confidence_warning() -> None:
    plan = _plan([_step("s1", "ingestion")])

    result = PlannerPlanValidator(confidence_threshold=0.5).validate(plan, {"ingestion"}, confidence=0.9)

    assert not any(issue.code == "low_confidence" for issue in result.warnings)


def test_structural_error_and_low_confidence_can_combine() -> None:
    plan = _plan([_step("s1", "ingestion"), _step("s2", "unknown_service", ["s1"])])

    result = PlannerPlanValidator(confidence_threshold=0.8).validate(plan, {"ingestion"}, confidence=0.3)

    assert result.is_valid is False
    codes = {issue.code for issue in result.issues}
    assert "unknown_node_name" in codes
    assert "low_confidence" in codes
