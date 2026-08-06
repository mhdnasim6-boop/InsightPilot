"""Request body for POST /collaboration/start.

Creates a session (``CollaborationService.create_session()``) and its
first delegation (``.delegate()``) in one call, then runs it
(``.run()``) — the REST-layer equivalent of "give the coordinator a
goal and the first agent to delegate to," so a caller never needs a
separate delegate round-trip just to get a session started. Additional
mid-run delegations (dynamic follow-ups) are always spawned internally
by ``CollaborationExecutor`` — see its own module docstring.
"""

from typing import Any

from pydantic import BaseModel, Field


class CollaborationStartRequest(BaseModel):
    """Body for POST /collaboration/start."""

    goal: str
    session_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    assigned_agent: str
    description: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class CollaborationDelegateRequest(BaseModel):
    """Body for POST /collaboration/{id}/delegate.

    Not in the phase spec's own literal REST list, but ``delegate()`` is
    one of ``CollaborationService``'s required public methods — added the
    same way Phase 29 added ``DELETE /memory`` beyond its own literal
    list, because the frontend's Delegation dashboard genuinely needs a
    way to add a subtask (e.g. ``report_agent`` depending on an
    already-delegated ``file_agent`` subtask) without which multi-agent
    workflows couldn't be built through the API at all.
    """

    assigned_agent: str
    description: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    reason: str = ""
