"""Autonomous optimization exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing — mirrors every other phase's own exception module.
"""

from backend.core.exceptions import InsightPilotError


class AutonomousError(InsightPilotError):
    """Base class for every autonomous-optimization-layer exception."""

    status_code = 500
    error_type = "AutonomousError"


class OptimizationReportNotFoundError(AutonomousError):
    """Raised when a report is looked up by an unknown report_id."""

    status_code = 404
    error_type = "OptimizationReportNotFoundError"
