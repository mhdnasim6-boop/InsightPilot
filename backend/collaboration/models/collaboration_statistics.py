"""CollaborationStatistics: aggregate counts across every collaboration session.

Mirrors ``MemoryStatistics``'s own shape — a plain, computed snapshot,
never persisted itself.
"""

from pydantic import BaseModel, Field


class CollaborationStatistics(BaseModel):
    """Aggregate counts over every tracked collaboration session."""

    total_sessions: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    total_subtasks: int = 0
    total_messages: int = 0
    total_delegations: int = 0
    total_negotiations: int = 0
    average_subtasks_per_session: float = 0.0
