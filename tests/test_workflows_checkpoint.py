"""Tests for build_workflow_checkpoint: a read-only composition over the
real ExecutionService/ApprovalService/ObservabilityService — no second
persistence mechanism.
"""

import asyncio

from pydantic import BaseModel

from backend.approval.services.approval_service import ApprovalService
from backend.approval.stores.approval_store import ApprovalStore
from backend.approval.stores.execution_history_store import ExecutionHistoryStore
from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore
from backend.execution.dispatcher.node_dispatcher import NodeDispatcher
from backend.execution.scheduler.dag_scheduler import DAGScheduler
from backend.execution.services.execution_service import ExecutionService
from backend.execution.services.task_registry import ExecutionTaskRegistry
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.stores.trace_store import TraceStore
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import InsightPilotState
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.utils.time import utc_now
from backend.workflows.execution.workflow_checkpoint import build_workflow_checkpoint
from backend.workflows.models.workflow_execution import WorkflowExecution
from backend.workflows.models.workflow_status import WorkflowStatus


class _FakeAgentNode(OrchestrationNode):
    def __init__(self, name: str) -> None:
        self.name = name

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state


class _Result(BaseModel):
    step_id: str
    status: str = "completed"
    execution_time: float = 0.01
    warnings: list[str] = []
    metadata: dict = {}


class _OkService:
    async def execute_step(self, step: object, session_id: str | None) -> _Result:
        return _Result(step_id=step.step_id)  # type: ignore[attr-defined]


def _plan(steps: list[ExecutionStep], plan_id: str = "p1") -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(plan_id=plan_id, status=PlanStatus.READY, created_at=now, updated_at=now, steps=steps)


def test_build_workflow_checkpoint_composes_real_state() -> None:
    node_dispatcher = NodeDispatcher()
    node_dispatcher.register("agent_a", _OkService())
    observability_service = ObservabilityService(TraceStore())
    scheduler = DAGScheduler(node_dispatcher, observability_service=observability_service)
    execution_service = ExecutionService(
        scheduler, ExecutionCheckpointStore(), ExecutionTaskRegistry(), observability_service,
    )
    approval_service = ApprovalService(ApprovalStore(), ExecutionHistoryStore())

    plan = _plan([ExecutionStep(step_id="a", name="A", node_name="agent_a")])

    async def scenario() -> WorkflowExecution:
        state = await execution_service.start(plan, session_id="s1")
        now = utc_now()
        return WorkflowExecution(
            workflow_execution_id="we1", workflow_id="w1", plan_id=plan.plan_id, execution_id=state.execution_id,
            session_id="s1", status=WorkflowStatus.COMPLETED, started_at=now, updated_at=now,
        )

    execution = asyncio.run(scenario())
    checkpoint = build_workflow_checkpoint(execution, execution_service, approval_service, observability_service)

    assert checkpoint.workflow_id == "w1"
    assert checkpoint.execution_id == execution.execution_id
    assert checkpoint.completed_agents == ["agent_a"]
    assert checkpoint.pending_agents == []
    assert checkpoint.failed_agents == []
    assert checkpoint.approval_state == []
    assert checkpoint.observability_trace_id is not None


def test_build_workflow_checkpoint_falls_back_to_recorded_ids_when_execution_id_is_none() -> None:
    node_dispatcher = NodeDispatcher()
    observability_service = ObservabilityService(TraceStore())
    scheduler = DAGScheduler(node_dispatcher, observability_service=observability_service)
    execution_service = ExecutionService(
        scheduler, ExecutionCheckpointStore(), ExecutionTaskRegistry(), observability_service,
    )
    approval_service = ApprovalService(ApprovalStore(), ExecutionHistoryStore())

    now = utc_now()
    execution = WorkflowExecution(
        workflow_execution_id="we1", workflow_id="w1", plan_id="p1", execution_id=None,
        status=WorkflowStatus.DRAFT, completed_steps=["a"], pending_steps=["b"], failed_steps=[],
        started_at=now, updated_at=now,
    )
    checkpoint = build_workflow_checkpoint(execution, execution_service, approval_service, observability_service)

    assert checkpoint.completed_agents == ["a"]
    assert checkpoint.pending_agents == ["b"]
