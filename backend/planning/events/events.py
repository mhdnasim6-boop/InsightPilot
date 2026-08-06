"""Plan lifecycle events."""

from datetime import datetime

from pydantic import BaseModel


class PlanningEvent(BaseModel):
    """Base class for all planning events."""

    plan_id: str
    timestamp: datetime


class PlanCreated(PlanningEvent):
    """A new plan has been registered with the planning service."""

    session_id: str | None = None


class PlanValidated(PlanningEvent):
    """A plan has finished validation."""

    is_valid: bool
    issue_count: int


class PlanStarted(PlanningEvent):
    """A plan has begun executing."""


class StepStarted(PlanningEvent):
    """A step within a plan has begun executing."""

    step_id: str
    node_name: str


class StepCompleted(PlanningEvent):
    """A step within a plan finished executing."""

    step_id: str
    duration_ms: float


class PlanCompleted(PlanningEvent):
    """A plan finished executing successfully."""

    status: str
    duration_ms: float


class PlanFailed(PlanningEvent):
    """A plan failed during execution."""

    error: str
    failed_step: str | None = None


class PlanPaused(PlanningEvent):
    """A plan's execution paused at an approval interrupt point (Phase 23, Human-in-the-Loop)."""

    step_id: str
    node_name: str


class PlanResumed(PlanningEvent):
    """A previously paused plan's execution resumed."""

    step_id: str
