"""Tests for ExecutionPlan, ExecutionStep, PlanStatus, and PlanMetrics."""

from typing import Any

import pytest
from pydantic import ValidationError

from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.enums import PlanStatus
from backend.planning.models.metrics import PlanMetrics
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.utils.time import utc_now


def _new_step(step_id: str = "s1", **overrides: Any) -> ExecutionStep:
    defaults: dict[str, Any] = {"step_id": step_id, "name": "Step", "node_name": "planner"}
    defaults.update(overrides)
    return ExecutionStep(**defaults)


def _new_plan(steps: list[ExecutionStep] | None = None, **overrides: Any) -> ExecutionPlan:
    now = utc_now()
    defaults: dict[str, Any] = {"plan_id": "p1", "created_at": now, "updated_at": now, "steps": steps or []}
    defaults.update(overrides)
    return ExecutionPlan(**defaults)


def test_execution_step_defaults_are_empty_and_pending() -> None:
    step = _new_step()
    assert step.inputs == {}
    assert step.outputs == {}
    assert step.dependencies == []
    assert step.metadata == {}
    assert step.status == ExecutionStatus.PENDING
    assert step.retry_policy.max_attempts == 1
    assert step.retry_policy.backoff_seconds == 0.0
    assert step.timeout is None


def test_execution_step_is_immutable() -> None:
    step = _new_step()
    with pytest.raises(ValidationError):
        step.status = ExecutionStatus.RUNNING


def test_execution_step_transition_via_model_copy() -> None:
    step = _new_step()
    updated = step.model_copy(update={"status": ExecutionStatus.COMPLETED})
    assert step.status == ExecutionStatus.PENDING
    assert updated.status == ExecutionStatus.COMPLETED


def test_execution_plan_defaults() -> None:
    plan = _new_plan()
    assert plan.status == PlanStatus.DRAFT
    assert plan.steps == []
    assert plan.metadata == {}
    assert plan.confidence is None
    assert plan.priority == 0
    assert plan.estimated_tokens is None
    assert plan.estimated_duration is None
    assert plan.estimated_cost is None


def test_execution_plan_is_immutable() -> None:
    plan = _new_plan()
    with pytest.raises(ValidationError):
        plan.status = PlanStatus.READY


def test_execution_plan_transition_via_model_copy_is_immutable() -> None:
    plan = _new_plan()
    updated = plan.model_copy(update={"status": PlanStatus.VALIDATED})
    assert plan.status == PlanStatus.DRAFT
    assert updated.status == PlanStatus.VALIDATED


def test_execution_plan_confidence_must_be_a_fraction() -> None:
    with pytest.raises(ValidationError):
        _new_plan(confidence=1.5)


def test_plan_status_values() -> None:
    assert {status.value for status in PlanStatus} == {
        "draft",
        "validated",
        "ready",
        "running",
        "paused",
        "completed",
        "failed",
        "cancelled",
    }


def test_plan_metrics_from_plan_copies_estimate_fields_only() -> None:
    plan = _new_plan(estimated_tokens=100, estimated_duration=12.5, estimated_cost=0.02)
    metrics = PlanMetrics.from_plan(plan)

    assert metrics.plan_id == plan.plan_id
    assert metrics.estimated_tokens == 100
    assert metrics.estimated_duration == 12.5
    assert metrics.estimated_cost == 0.02
    assert metrics.estimated_parallelism is None
