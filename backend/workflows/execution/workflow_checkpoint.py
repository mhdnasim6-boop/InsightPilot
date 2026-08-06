"""WorkflowCheckpoint: a read-only, on-demand composition over the real
ExecutionCheckpoint/ApprovalService/ObservabilityService — never a
second persistence mechanism.

Reuses the existing execution checkpoint concept literally:
``ExecutionService.get()`` already returns the authoritative
``ExecutionState`` (completed/pending/failed steps) from the real
``ExecutionCheckpointStore``; this module only *composes* that with
approval state and the observability trace id into the one snapshot
shape this phase's own spec names — completed agents, pending agents,
approval state, memory references, and observability trace ids.
"""

from datetime import datetime

from pydantic import BaseModel

from backend.approval.models.approval import ExecutionApproval
from backend.approval.services.approval_service import ApprovalService
from backend.execution.services.execution_service import ExecutionService
from backend.execution.state.node_status import NodeStatus
from backend.observability.services.observability_service import ObservabilityService
from backend.utils.time import utc_now
from backend.workflows.models.workflow_execution import WorkflowExecution


class WorkflowCheckpoint(BaseModel):
    """A composed, point-in-time snapshot of one workflow execution's real state."""

    workflow_id: str
    workflow_execution_id: str
    execution_id: str | None
    plan_id: str
    status: str
    completed_agents: list[str]
    pending_agents: list[str]
    failed_agents: list[str]
    approval_state: list[ExecutionApproval]
    memory_references: list[str]
    observability_trace_id: str | None
    checkpointed_at: datetime


def build_workflow_checkpoint(
    execution: WorkflowExecution,
    execution_service: ExecutionService,
    approval_service: ApprovalService,
    observability_service: ObservabilityService | None = None,
) -> WorkflowCheckpoint:
    """Compose a WorkflowCheckpoint from every real subsystem's own current state.

    ``completed_agents``/``pending_agents``/``failed_agents`` are the
    *node names* of steps in each state (not step_ids) — read straight
    from the real ``ExecutionState`` if the underlying execution is still
    tracked, falling back to the last values recorded on ``execution``
    itself (by step_id, since a settled/forgotten checkpoint no longer
    carries node names) otherwise.
    """
    completed, pending, failed = execution.completed_steps, execution.pending_steps, execution.failed_steps
    if execution.execution_id is not None:
        try:
            state = execution_service.get(execution.execution_id)
        except Exception:  # noqa: BLE001 - a settled/evicted checkpoint falls back to the last recorded ids
            state = None
        if state is not None:
            completed = [state.steps[sid].node_name for sid in state.step_ids_with_status(NodeStatus.COMPLETED)]
            pending = [
                state.steps[sid].node_name
                for sid in state.step_ids_with_status(NodeStatus.PENDING, NodeStatus.QUEUED, NodeStatus.RUNNING)
            ]
            failed = [state.steps[sid].node_name for sid in state.step_ids_with_status(NodeStatus.FAILED)]

    trace_id = execution.trace_id
    if trace_id is None and observability_service is not None:
        trace_id = observability_service.trace_id_for_plan(execution.plan_id)

    return WorkflowCheckpoint(
        workflow_id=execution.workflow_id, workflow_execution_id=execution.workflow_execution_id,
        execution_id=execution.execution_id, plan_id=execution.plan_id, status=execution.status.value,
        completed_agents=completed, pending_agents=pending, failed_agents=failed,
        approval_state=approval_service.list_for_plan(execution.plan_id),
        memory_references=execution.memory_ids, observability_trace_id=trace_id, checkpointed_at=utc_now(),
    )
