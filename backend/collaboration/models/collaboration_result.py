"""CollaborationResult: the final, terminal outcome of one collaboration session."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.planning.models.enums import PlanStatus


class CollaborationResult(BaseModel):
    """A terminal collaboration session's summary — recorded once, never updated."""

    model_config = ConfigDict(frozen=True)

    collaboration_id: str
    goal: str
    status: PlanStatus
    completed_subtasks: list[str] = Field(default_factory=list)
    failed_subtasks: list[str] = Field(default_factory=list)
    artifacts_produced: list[str] = Field(default_factory=list)
    total_messages: int = 0
    total_delegations: int = 0
    duration_seconds: float = 0.0
    created_at: datetime
