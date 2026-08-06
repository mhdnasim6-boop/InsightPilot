"""Planning-layer exception hierarchy."""

from backend.core.exceptions import InsightPilotError


class PlanningError(InsightPilotError):
    """Base class for all planning-layer exceptions."""

    status_code = 500
    error_type = "PlanningError"


class PlanNotReadyError(PlanningError):
    """Raised when an operation requires a plan status it doesn't currently have."""

    status_code = 422
    error_type = "PlanNotReadyError"


class PlanNotPausedError(PlanningError):
    """Raised when resuming/rejecting/cancelling a plan that has no paused execution (Phase 23)."""

    status_code = 409
    error_type = "PlanNotPausedError"
