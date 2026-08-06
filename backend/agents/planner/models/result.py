"""PlannerAgentResult: the Planner Agent's complete, structured answer for one ExecutionStep.

``planner_output`` reuses ``PlannerOutput`` directly — never redefined —
the same reuse relationship ``ReportAgentResult`` has with
``ReportDocument``. ``status`` reuses
``backend.orchestration.state.state.ExecutionStatus``, same as every
other agent. A generated ``PlannerOutput.execution_plan`` is always
``DRAFT`` status — the Planner never executes it; that stays
``PlanningService``/``OrchestrationService``'s job.
"""

from typing import Any

from pydantic import BaseModel, Field

from backend.agents.planner.models.io import PlannerOutput
from backend.orchestration.state.state import ExecutionStatus


class PlannerAgentResult(BaseModel):
    """The complete outcome of one PlannerAgent run: the plan it produced, or why it couldn't."""

    step_id: str
    status: ExecutionStatus
    planner_output: PlannerOutput | None = None
    warnings: list[str] = Field(default_factory=list)
    execution_time: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
