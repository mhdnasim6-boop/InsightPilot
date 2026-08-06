"""WorkflowStep: one unit of work within a WorkflowDefinition.

Deliberately the same shape as ``backend.planning.models.step.ExecutionStep``
(``dependencies``/``retry_policy``/``inputs``/``timeout``) — not a
duplication of its logic, a structural DTO the workflow layer converts
1:1 into a real ``ExecutionStep`` before anything is validated/optimized/
executed (see ``WorkflowBuilder.build_plan()``). Every actual dependency-
ordering, retry, and dispatch decision still happens inside the existing
planning/execution engines, never re-implemented here.

``kind`` records what this step names in ``node_name`` — today only
``"agent"`` steps are actually schedulable (the orchestration graph has
no tool-level or plugin-level DAG nodes; agents call tools internally).
``tool``/``plugin`` are accepted values reserved for future extension
(see README's own Future Extensions) and rejected by
``WorkflowValidator`` if ever submitted for real execution today — not a
placeholder implementation, an honest, enforced scope boundary.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.planning.models.retry_policy import StepRetryPolicy

WorkflowStepKind = Literal["agent", "tool", "plugin"]


class WorkflowStep(BaseModel):
    """One node invocation within a workflow, pre-conversion to a real ExecutionStep."""

    model_config = ConfigDict(frozen=True)

    step_id: str
    name: str
    description: str | None = None
    node_name: str
    kind: WorkflowStepKind = "agent"
    inputs: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    retry_policy: StepRetryPolicy = Field(default_factory=StepRetryPolicy)
    timeout: float | None = None
