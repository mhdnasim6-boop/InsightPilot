"""RemoteExecution: the execution-credit record created once a RoutingDecision dispatches.

Mirrors the Lease/TaskAssignment split from Phase 38 one layer up:
`RoutingDecision` is the (reroutable-while-PENDING) scheduling verdict;
`RemoteExecution` is the terminal, dispatch-time-onward credit record —
created the moment a decision transitions to DISPATCHED, closed via
``complete()``/``fail()``, never rerouted.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class RemoteExecutionStatus(str, Enum):
    """Lifecycle of one RemoteExecution."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RemoteExecution(BaseModel):
    """One workflow execution credited to one cluster, from dispatch to completion."""

    model_config = ConfigDict(frozen=True)

    remote_execution_id: str
    decision_id: str
    cluster_id: str
    workflow_id: str
    plan_id: str | None = None
    status: RemoteExecutionStatus = RemoteExecutionStatus.RUNNING
    started_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
