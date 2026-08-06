"""CollaborationTask/SubTask: the coordinator's own task graph.

``SubTask.status`` reuses ``NodeStatus`` directly (a SubTask becomes
exactly one ``ExecutionStep`` dispatched through the existing
``ExecutionService``, so its lifecycle *is* a DAG node's lifecycle —
no second near-identical enum). ``CollaborationTask.status`` reuses
``PlanStatus`` the same way ``ExecutionState.status`` already does.

Immutable, like every other state snapshot in this codebase
(``ExecutionState``/``ExecutionPlan``): the coordinator produces a new
snapshot via ``model_copy`` on every transition, never in-place mutation.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.execution.state.node_status import NodeStatus
from backend.planning.models.enums import PlanStatus


class SubTask(BaseModel):
    """One unit of delegated work within a CollaborationTask."""

    model_config = ConfigDict(frozen=True)

    subtask_id: str
    description: str
    assigned_agent: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    requested_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollaborationTask(BaseModel):
    """The complete, point-in-time snapshot of one collaboration session."""

    model_config = ConfigDict(frozen=True)

    collaboration_id: str
    session_id: str | None = None
    goal: str
    status: PlanStatus = PlanStatus.DRAFT
    subtasks: dict[str, SubTask] = Field(default_factory=dict)
    subtask_order: list[str] = Field(default_factory=list)
    active_execution_id: str | None = None
    created_at: datetime
    updated_at: datetime

    def subtask_ids_with_status(self, *statuses: NodeStatus) -> list[str]:
        """Return subtask_ids currently in any of ``statuses``, in insertion order."""
        return [
            subtask_id
            for subtask_id in self.subtask_order
            if self.subtasks[subtask_id].status in statuses
        ]
