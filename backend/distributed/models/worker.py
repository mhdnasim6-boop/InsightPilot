"""Worker: one registered execution worker and everything known about it.

Immutable like every other lifecycle model in this codebase
(``ExecutionApproval``, ``WorkflowExecution``) — a state transition
(heartbeat, drain, assign a task) produces a new instance via
``model_copy``, never in-place mutation, so ``WorkerRegistry`` can hand
out a snapshot with no risk of a caller mutating shared state.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.distributed.models.worker_capability import WorkerCapability
from backend.distributed.models.worker_status import WorkerStatus


class Worker(BaseModel):
    """One registered worker: identity, capacity, capabilities, and current load."""

    model_config = ConfigDict(frozen=True)

    worker_id: str
    hostname: str
    status: WorkerStatus = WorkerStatus.ONLINE
    last_heartbeat: datetime | None = None
    capabilities: list[WorkerCapability] = Field(default_factory=list)
    active_tasks: list[str] = Field(default_factory=list)
    maximum_parallel_tasks: int = Field(default=1, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    registered_at: datetime | None = None

    def supports(self, node_name: str) -> bool:
        """Whether this worker advertises the given node_name as a capability."""
        return any(capability.node_name == node_name for capability in self.capabilities)

    def has_capacity(self) -> bool:
        """Whether this worker can accept one more task right now."""
        return len(self.active_tasks) < self.maximum_parallel_tasks

    def load_ratio(self) -> float:
        """Fraction of capacity currently in use — 0.0 (idle) to 1.0 (full)."""
        return len(self.active_tasks) / self.maximum_parallel_tasks
