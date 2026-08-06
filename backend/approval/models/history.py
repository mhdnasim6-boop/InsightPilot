"""ExecutionHistoryEvent: one entry in a plan's HITL lifecycle timeline.

Distinct from ``ExecutionApproval`` (a single decision's current state):
history is an append-only log of everything that happened to a plan's
execution across possibly many approvals — a plan can wait, get
approved, resume, wait again at the next gate, and so on. Reuses no
existing event model since ``PlanEventBus``'s own events
(``PlanStarted``/``PlanCompleted``/...) are transient pub/sub messages,
never stored for later listing — this is a queryable, persisted-in-memory
timeline instead.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExecutionHistoryEventType(str, Enum):
    """Every HITL lifecycle event this phase tracks, per the task's explicit list."""

    WAITING = "waiting"
    APPROVED = "approved"
    REJECTED = "rejected"
    RESUMED = "resumed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class ExecutionHistoryEvent(BaseModel):
    """One immutable timeline entry for a plan's HITL execution history."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    plan_id: str
    step_id: str | None = None
    approval_id: str | None = None
    event_type: ExecutionHistoryEventType
    timestamp: datetime
    actor: str | None = None
    detail: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
