"""Workflow exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing — mirrors every other phase's own exception module
(``backend.security.exceptions``/``backend.operations.exceptions``).
"""

from backend.core.exceptions import InsightPilotError


class WorkflowError(InsightPilotError):
    """Base class for every workflow-layer exception."""

    status_code = 500
    error_type = "WorkflowError"


class WorkflowNotFoundError(WorkflowError):
    """Raised when a workflow is looked up by an unregistered workflow_id."""

    status_code = 404
    error_type = "WorkflowNotFoundError"


class WorkflowExecutionNotFoundError(WorkflowError):
    """Raised when a workflow execution is looked up by an unregistered id."""

    status_code = 404
    error_type = "WorkflowExecutionNotFoundError"


class WorkflowValidationError(WorkflowError):
    """Raised when a workflow's structure or step graph fails validation."""

    status_code = 422
    error_type = "WorkflowValidationError"


class WorkflowCycleError(WorkflowValidationError):
    """Raised when a workflow's steps contain a dependency cycle."""

    error_type = "WorkflowCycleError"


class WorkflowNotReadyError(WorkflowError):
    """Raised when execute()/optimize() is attempted on a workflow in the wrong lifecycle state."""

    status_code = 422
    error_type = "WorkflowNotReadyError"


class WorkflowNotPausedError(WorkflowError):
    """Raised when resume() is attempted on a workflow execution that isn't paused."""

    status_code = 422
    error_type = "WorkflowNotPausedError"


class UnknownAgentError(WorkflowValidationError):
    """Raised when a step's node_name isn't a dynamically discovered, real agent."""

    error_type = "UnknownAgentError"
