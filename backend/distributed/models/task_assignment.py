"""TaskAssignment: one step credited to one worker.

Mirrors ``ExecutionApproval``'s own shape (one lifecycle record per
gated event, immutable, ``model_copy``'d on transition). A
``TaskAssignment`` never carries the step's own input/output payload —
that already lives in the real ``ExecutionState``/``ExecutionCheckpoint``
this phase reuses; this is bookkeeping for *which worker* a step is
credited to, not a second copy of execution state.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class TaskAssignmentStatus(str, Enum):
    """Lifecycle of one TaskAssignment."""

    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    REQUEUED = "requeued"


class TaskAssignment(BaseModel):
    """One step assigned to one worker, with its own lifecycle independent of the step's own execution record."""

    model_config = ConfigDict(frozen=True)

    assignment_id: str
    step_id: str
    plan_id: str | None = None
    node_name: str
    worker_id: str
    lease_id: str
    status: TaskAssignmentStatus = TaskAssignmentStatus.ASSIGNED
    assigned_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    retry_count: int = 0
