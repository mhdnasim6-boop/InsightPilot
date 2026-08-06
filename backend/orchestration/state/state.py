"""The single, strongly-typed state model threaded through every orchestration graph."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from backend.ai.models.responses import TokenUsage


class ExecutionStatus(str, Enum):
    """Lifecycle states of a graph execution.

    ``SKIPPED`` is distinct from ``FAILED``: it means a node had nothing
    to do (e.g. BrowserAgent given no search-relevant input) rather than
    attempting something and failing at it. A node reporting SKIPPED
    never contributes to ``state.errors`` — see ``BrowserAgentNode``.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class InsightPilotState(BaseModel):
    """Central state passed between every node in every orchestration graph.

    Intentionally generic — no business-specific fields (no dataset,
    query, or report concepts here). Every future node (planner, file,
    SQL, analysis, ...) reads and writes this one shape instead of each
    inventing its own.
    """

    # Identity
    session_id: str | None = None
    execution_id: str

    # Conversation context. ``conversation_history`` is prior context
    # seeded before this execution starts; ``messages`` accumulates
    # during this specific run.
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    user_request: str | None = None
    intent: str | None = None

    # Working data — generic containers any node may read/write.
    artifacts: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Execution bookkeeping
    errors: list[str] = Field(default_factory=list)
    execution_trace: list[str] = Field(default_factory=list)
    current_node: str | None = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    token_usage: TokenUsage = Field(default_factory=TokenUsage)

    # Timestamps
    created_at: datetime
    updated_at: datetime
