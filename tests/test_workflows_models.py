"""Tests for backend.workflows.models: shapes, defaults, immutability."""

import pytest
from pydantic import ValidationError

from backend.utils.time import utc_now
from backend.workflows.models.workflow import Workflow
from backend.workflows.models.workflow_definition import WorkflowDefinition
from backend.workflows.models.workflow_execution import WorkflowExecution
from backend.workflows.models.workflow_statistics import WorkflowStatistics
from backend.workflows.models.workflow_status import WorkflowStatus
from backend.workflows.models.workflow_step import WorkflowStep


def test_workflow_status_has_every_documented_value() -> None:
    expected = {
        "draft", "validated", "optimized", "ready", "running", "paused", "completed", "failed", "cancelled",
    }
    assert {status.value for status in WorkflowStatus} == expected


def test_workflow_step_defaults() -> None:
    step = WorkflowStep(step_id="s1", name="Step 1", node_name="file_agent")
    assert step.kind == "agent"
    assert step.dependencies == []
    assert step.inputs == {}
    assert step.retry_policy.max_attempts == 1


def test_workflow_step_is_frozen() -> None:
    step = WorkflowStep(step_id="s1", name="Step 1", node_name="file_agent")
    with pytest.raises(ValidationError):
        step.name = "changed"  # type: ignore[misc]


def test_workflow_definition_defaults() -> None:
    definition = WorkflowDefinition(name="Test")
    assert definition.description == ""
    assert definition.steps == []
    assert definition.tags == []


def test_workflow_defaults() -> None:
    now = utc_now()
    workflow = Workflow(
        workflow_id="w1", definition=WorkflowDefinition(name="Test"), created_at=now, updated_at=now,
    )
    assert workflow.status == WorkflowStatus.DRAFT
    assert workflow.version == 1
    assert workflow.cloned_from is None
    assert workflow.plan_id is None


def test_workflow_execution_defaults() -> None:
    now = utc_now()
    execution = WorkflowExecution(
        workflow_execution_id="e1", workflow_id="w1", plan_id="p1", started_at=now, updated_at=now,
    )
    assert execution.status == WorkflowStatus.RUNNING
    assert execution.pause_reason is None
    assert execution.memory_ids == []
    assert execution.completed_steps == []
    assert execution.completed_at is None


def test_workflow_statistics_defaults() -> None:
    stats = WorkflowStatistics()
    assert stats.total_workflows == 0
    assert stats.by_status == {}
    assert stats.average_duration_seconds == 0.0
