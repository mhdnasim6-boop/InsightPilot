"""WorkflowExecution: one run of a Workflow — a record referencing the
real subsystems' own ids (the underlying ExecutionService execution_id,
the ObservabilityService trace_id, the AdaptivePlanningService
optimization_id, the ReflectionService reflection_id, and every Memory
id written along the way), not a re-implementation of any of them.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.workflows.models.workflow_status import WorkflowStatus

PauseReason = Literal["approval", "manual"]


class WorkflowExecution(BaseModel):
    """One execution attempt of a Workflow, and every real subsystem id it touched."""

    model_config = ConfigDict(frozen=True)

    workflow_execution_id: str
    workflow_id: str
    plan_id: str
    execution_id: str | None = None
    session_id: str | None = None
    status: WorkflowStatus = WorkflowStatus.RUNNING
    pause_reason: PauseReason | None = None
    trace_id: str | None = None
    optimization_id: str | None = None
    reflection_id: str | None = None
    memory_ids: list[str] = Field(default_factory=list)
    completed_steps: list[str] = Field(default_factory=list)
    pending_steps: list[str] = Field(default_factory=list)
    failed_steps: list[str] = Field(default_factory=list)
    error: str | None = None
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
