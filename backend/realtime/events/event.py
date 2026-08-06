"""Event: one typed, immutable fact published through RealtimeService.

A single concrete model (not 24 subclasses, unlike
``backend.orchestration.events.events.OrchestrationEvent``) — with 24
event types spanning 8 unrelated subsystems, a common correlation
envelope plus a free-form ``data`` payload is simpler and no less typed
(``event_type`` is still a closed ``EventType`` enum) than a 24-class
hierarchy would be, and is exactly what a generic cross-subsystem
transport layer needs: every consumer (WebSocket client, replay buffer,
REST endpoint) can filter/display on the common fields without knowing
each event type's own payload shape.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.realtime.events.event_type import EventType
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class Event(BaseModel):
    """One immutable, typed realtime event."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=generate_id)
    event_type: EventType
    timestamp: datetime = Field(default_factory=utc_now)

    workflow_id: str | None = None
    execution_id: str | None = None
    plan_id: str | None = None
    step_id: str | None = None
    trace_id: str | None = None
    agent_name: str | None = None
    tool_name: str | None = None
    user_id: str | None = None

    data: dict[str, Any] = Field(default_factory=dict)
