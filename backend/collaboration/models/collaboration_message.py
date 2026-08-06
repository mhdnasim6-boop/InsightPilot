"""AgentMessage: the only unit of communication passed through MessageBus.

Agents never call each other directly in this architecture — every
delegation request, artifact-ready notice, or follow-up subtask request
is recorded as one of these, so ``MessageBus.history()`` is a complete,
replayable audit trail of a collaboration session.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageType(str, Enum):
    """What kind of communication one AgentMessage represents."""

    DELEGATION_REQUEST = "delegation_request"
    ARTIFACT_READY = "artifact_ready"
    SUBTASK_REQUEST = "subtask_request"
    STATUS_UPDATE = "status_update"
    INFO = "info"


class AgentMessage(BaseModel):
    """One message exchanged through the MessageBus. ``to_agent=None`` means broadcast."""

    model_config = ConfigDict(frozen=True)

    message_id: str
    collaboration_id: str
    from_agent: str
    to_agent: str | None = None
    message_type: MessageType
    content: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
