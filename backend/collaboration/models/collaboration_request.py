"""CollaborationRequest: the domain input to CollaborationService.create_session().

Deliberately just a goal plus optional context — never a fully expanded
execution graph. Mirrors ``PlannerInput`` being the Planner's own
"what to understand," not "what to run": expansion into SubTasks happens
afterward, via ``delegate()``/``spawn_subtask()``, dynamically.
"""

from typing import Any

from pydantic import BaseModel, Field


class CollaborationRequest(BaseModel):
    """A high-level goal to collaborate on — not a pre-enumerated step list."""

    goal: str
    session_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
