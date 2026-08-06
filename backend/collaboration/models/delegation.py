"""Delegation: a record of the coordinator assigning one SubTask to one agent."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Delegation(BaseModel):
    """One coordinator -> agent assignment."""

    model_config = ConfigDict(frozen=True)

    delegation_id: str
    collaboration_id: str
    subtask_id: str
    from_agent: str
    to_agent: str
    reason: str
    created_at: datetime
