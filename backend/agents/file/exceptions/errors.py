"""FileAgent exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing.
"""

from backend.core.exceptions import InsightPilotError


class FileAgentError(InsightPilotError):
    """Base class for every FileAgent-related exception."""

    status_code = 500
    error_type = "FileAgentError"


class InvalidAgentInputError(FileAgentError):
    """Raised when the given ExecutionStep/session don't carry what FileAgent needs to run.

    Raised immediately, before any service is called — a malformed
    request, not a legitimate pipeline failure. Contrast with a
    downstream service failing (missing file, corrupt data): that is
    captured in a FAILED ``AgentExecutionResult``, never raised.
    """

    status_code = 422
    error_type = "InvalidAgentInputError"


class AgentExecutionNotFoundError(FileAgentError):
    """Raised when a requested step_id has no stored AgentExecutionResult."""

    status_code = 404
    error_type = "AgentExecutionNotFoundError"
