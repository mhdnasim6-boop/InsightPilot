"""Tests for the workflow exporters: JSON, Markdown, and Mermaid — the
Mermaid exporter reuses the two real, existing Mermaid generators
directly (never a third implementation).
"""

import asyncio
import json

from pydantic import BaseModel

from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore
from backend.execution.dispatcher.node_dispatcher import NodeDispatcher
from backend.execution.scheduler.dag_scheduler import DAGScheduler
from backend.execution.services.execution_service import ExecutionService
from backend.execution.services.task_registry import ExecutionTaskRegistry
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.utils.time import utc_now
from backend.workflows.exporters.json_exporter import export_workflow_json
from backend.workflows.exporters.markdown_exporter import export_workflow_markdown
from backend.workflows.exporters.mermaid_exporter import export_workflow_mermaid
from backend.workflows.models.workflow import Workflow
from backend.workflows.models.workflow_definition import WorkflowDefinition
from backend.workflows.models.workflow_execution import WorkflowExecution
from backend.workflows.models.workflow_status import WorkflowStatus
from backend.workflows.models.workflow_step import WorkflowStep


class _Result(BaseModel):
    step_id: str
    status: str = "completed"
    execution_time: float = 0.01
    warnings: list[str] = []
    metadata: dict = {}


class _OkService:
    async def execute_step(self, step: object, session_id: str | None) -> _Result:
        return _Result(step_id=step.step_id)  # type: ignore[attr-defined]


def _workflow() -> Workflow:
    now = utc_now()
    definition = WorkflowDefinition(
        name="Test Workflow", description="desc", steps=[WorkflowStep(step_id="a", name="A", node_name="agent_a")],
        tags=["t1"],
    )
    return Workflow(workflow_id="w1", definition=definition, status=WorkflowStatus.DRAFT, created_at=now, updated_at=now)


def test_export_workflow_json_includes_workflow_and_null_execution() -> None:
    payload = json.loads(export_workflow_json(_workflow(), None))
    assert payload["workflow"]["workflow_id"] == "w1"
    assert payload["latest_execution"] is None


def test_export_workflow_json_includes_the_latest_execution() -> None:
    now = utc_now()
    execution = WorkflowExecution(
        workflow_execution_id="we1", workflow_id="w1", plan_id="p1", status=WorkflowStatus.COMPLETED,
        started_at=now, updated_at=now,
    )
    payload = json.loads(export_workflow_json(_workflow(), execution))
    assert payload["latest_execution"]["workflow_execution_id"] == "we1"


def test_export_workflow_markdown_includes_name_and_steps() -> None:
    markdown = export_workflow_markdown(_workflow(), None)
    assert "# Workflow: Test Workflow" in markdown
    assert "| a | A | agent_a |" in markdown


def test_export_workflow_markdown_includes_execution_section_when_given() -> None:
    now = utc_now()
    execution = WorkflowExecution(
        workflow_execution_id="we1", workflow_id="w1", plan_id="p1", status=WorkflowStatus.COMPLETED,
        completed_steps=["a"], started_at=now, updated_at=now,
    )
    markdown = export_workflow_markdown(_workflow(), execution)
    assert "## Latest Execution" in markdown
    assert "we1" in markdown


def test_export_workflow_mermaid_renders_the_plain_structure_with_no_execution() -> None:
    mermaid = export_workflow_mermaid(_workflow(), None, execution_service=None)  # type: ignore[arg-type]
    assert "graph TD;" in mermaid
    assert 'a["A"]' in mermaid


def test_export_workflow_mermaid_renders_status_highlighting_with_a_real_execution() -> None:
    node_dispatcher = NodeDispatcher()
    node_dispatcher.register("agent_a", _OkService())
    scheduler = DAGScheduler(node_dispatcher)
    execution_service = ExecutionService(scheduler, ExecutionCheckpointStore(), ExecutionTaskRegistry())

    now = utc_now()
    plan = ExecutionPlan(
        plan_id="p1", status=PlanStatus.READY, created_at=now, updated_at=now,
        steps=[ExecutionStep(step_id="a", name="A", node_name="agent_a")],
    )
    state = asyncio.run(execution_service.start(plan, session_id="s1"))

    execution = WorkflowExecution(
        workflow_execution_id="we1", workflow_id="w1", plan_id="p1", execution_id=state.execution_id,
        status=WorkflowStatus.COMPLETED, started_at=now, updated_at=now,
    )
    mermaid = export_workflow_mermaid(_workflow(), execution, execution_service)
    assert "class a completed;" in mermaid
