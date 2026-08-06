"""Collaboration exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing — mirrors ``backend.execution.exceptions``/
``backend.memory.exceptions``.
"""

from backend.core.exceptions import InsightPilotError


class CollaborationError(InsightPilotError):
    """Base class for every collaboration-layer exception."""

    status_code = 500
    error_type = "CollaborationError"


class CollaborationNotFoundError(CollaborationError):
    """Raised when a collaboration is looked up by an unregistered collaboration_id."""

    status_code = 404
    error_type = "CollaborationNotFoundError"


class SubTaskNotFoundError(CollaborationError):
    """Raised when a subtask is looked up by an unregistered subtask_id."""

    status_code = 404
    error_type = "SubTaskNotFoundError"


class UnknownAgentError(CollaborationError):
    """Raised when a delegation targets an agent with no registered capability."""

    status_code = 422
    error_type = "UnknownAgentError"


class CollaborationNotPausedError(CollaborationError):
    """Raised when resuming/cancelling a collaboration that isn't in a resumable state."""

    status_code = 409
    error_type = "CollaborationNotPausedError"
