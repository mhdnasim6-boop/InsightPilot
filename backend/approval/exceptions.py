"""Approval framework exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing. A flat module, not a package — mirrors
``backend.agents.planner.exceptions``/``backend.tools.exceptions``: this
phase's own error surface is small enough not to need a sub-package.
"""

from backend.core.exceptions import InsightPilotError


class ApprovalError(InsightPilotError):
    """Base class for every approval-framework exception."""

    status_code = 500
    error_type = "ApprovalError"


class ApprovalNotFoundError(ApprovalError):
    """Raised when an approval is looked up by an unregistered approval_id."""

    status_code = 404
    error_type = "ApprovalNotFoundError"


class ApprovalAlreadyDecidedError(ApprovalError):
    """Raised when approving/rejecting an approval that isn't PENDING anymore."""

    status_code = 409
    error_type = "ApprovalAlreadyDecidedError"


class NoPausedExecutionError(ApprovalError):
    """Raised when resuming/cancelling a plan that has no paused execution to act on."""

    status_code = 409
    error_type = "NoPausedExecutionError"
