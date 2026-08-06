"""The strongly typed, first-class representation of a unit of planned work."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.planning.models.enums import PlanStatus
from backend.planning.models.step import ExecutionStep


class ExecutionPlan(BaseModel):
    """A complete, structured plan: a goal broken into ordered, dependent steps.

    Immutable by design (``frozen=True``) — every lifecycle transition
    (validate/optimize/execute) produces a new plan via ``model_copy``,
    exactly like ``InsightPilotState``. A future Planner agent's only job
    is to construct one of these; everything else in this package works
    from it without knowing how it was produced.
    """

    model_config = ConfigDict(frozen=True)

    plan_id: str
    session_id: str | None = None
    execution_id: str | None = None
    user_request: str | None = None
    goal: str | None = None
    status: PlanStatus = PlanStatus.DRAFT
    priority: int = Field(default=0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    estimated_duration: float | None = None
    estimated_tokens: int | None = None
    estimated_cost: float | None = None
    steps: list[ExecutionStep] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
