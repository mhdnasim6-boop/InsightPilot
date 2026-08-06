"""NegotiationDecision: a record of the coordinator deduplicating a shared artifact need.

Produced whenever two or more subtasks would otherwise both produce the
same artifact (same agent, same inputs) — the coordinator executes the
producer only once and redirects every other requester to depend on it
instead, recording why here.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NegotiationDecision(BaseModel):
    """One dependency-negotiation outcome: several requesters, one producer."""

    model_config = ConfigDict(frozen=True)

    negotiation_id: str
    collaboration_id: str
    requested_by: list[str] = Field(default_factory=list)
    resolved_producer_subtask_id: str
    reason: str
    created_at: datetime
