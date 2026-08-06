"""A single unit of work within an ExecutionPlan."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.retry_policy import StepRetryPolicy


class ExecutionStep(BaseModel):
    """One node invocation within a plan.

    ``dependencies`` (other step_ids that must complete first) is what
    lets steps with no dependency on each other run in parallel in a
    future executor — this phase only records the dependency graph, it
    doesn't yet schedule steps concurrently. Immutable like
    ``InsightPilotState``: lifecycle changes (e.g. ``status``) happen via
    ``model_copy``, never in-place mutation.
    """

    model_config = ConfigDict(frozen=True)

    step_id: str
    name: str
    description: str | None = None
    node_name: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    retry_policy: StepRetryPolicy = Field(default_factory=StepRetryPolicy)
    timeout: float | None = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    metadata: dict[str, Any] = Field(default_factory=dict)
