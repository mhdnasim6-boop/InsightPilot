"""Adaptive planning exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing — mirrors ``backend.reflection.exceptions``/
``backend.collaboration.exceptions``.
"""

from backend.core.exceptions import InsightPilotError


class AdaptivePlanningError(InsightPilotError):
    """Base class for every adaptive-planning exception."""

    status_code = 500
    error_type = "AdaptivePlanningError"


class OptimizationNotFoundError(AdaptivePlanningError):
    """Raised when an optimization is looked up by an unregistered optimization_id."""

    status_code = 404
    error_type = "OptimizationNotFoundError"
