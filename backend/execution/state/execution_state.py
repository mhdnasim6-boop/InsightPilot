"""ExecutionState: the complete, point-in-time snapshot of one DAG execution.

Immutable, like ``ExecutionPlan``/``ExecutionTrace`` — every transition
produces a new snapshot via ``model_copy``, never in-place mutation.
``DAGScheduler`` holds a plain ``dict[execution_id, ExecutionState]`` and
replaces the value wholesale on every tick, mirroring exactly how
``PlanExecutor`` holds ``self._plans: dict[str, ExecutionPlan]``. ``status``
reuses ``PlanStatus`` directly — an execution's overall status *is* the
plan's status, same reasoning ``ExecutionTrace`` already established.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.execution.state.node_status import NodeStatus
from backend.planning.models.enums import PlanStatus


class StepExecutionState(BaseModel):
    """One step's own progress within a DAG execution.

    ``approved`` is set once (by ``DAGScheduler.resume()``, after a human
    grants the pending ``ExecutionApproval``) and never re-checked
    against the active ``ApprovalPolicy`` again — an ``ApprovalPolicy``
    is a standing rule ("pause every SQL step"), not a one-time gate, so
    without this flag a step approved once would be re-paused forever
    every time the scheduler re-evaluates it as runnable.
    """

    model_config = ConfigDict(frozen=True)

    step_id: str
    node_name: str
    status: NodeStatus = NodeStatus.PENDING
    attempts: int = 0
    approved: bool = False
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExecutionState(BaseModel):
    """The complete snapshot of one plan's DAG execution: every step's own progress."""

    model_config = ConfigDict(frozen=True)

    execution_id: str
    plan_id: str
    session_id: str | None = None
    status: PlanStatus
    steps: dict[str, StepExecutionState] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    def step_ids_with_status(self, *statuses: NodeStatus) -> list[str]:
        """Return step_ids currently in any of ``statuses``, in insertion order."""
        return [step_id for step_id, step in self.steps.items() if step.status in statuses]
