"""Execution engine exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing — mirrors ``backend.observability.exceptions``/
``backend.approval.exceptions``.
"""

from backend.core.exceptions import InsightPilotError


class ExecutionError(InsightPilotError):
    """Base class for every execution-engine exception."""

    status_code = 500
    error_type = "ExecutionError"


class ExecutionNotFoundError(ExecutionError):
    """Raised when an execution is looked up by an unregistered execution_id."""

    status_code = 404
    error_type = "ExecutionNotFoundError"


class ExecutionNotPausedError(ExecutionError):
    """Raised when resuming/cancelling an execution that isn't in a resumable state."""

    status_code = 409
    error_type = "ExecutionNotPausedError"


class UnknownNodeError(ExecutionError):
    """Raised when a step's node_name has no registered agent service in NodeDispatcher."""

    status_code = 422
    error_type = "UnknownNodeError"
