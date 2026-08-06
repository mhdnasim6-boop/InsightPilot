"""Tool Layer exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing. A flat module, not a package — mirrors
``backend.agents.planner.exceptions``: the Tool Layer's own error
surface (today: only "unknown tool name") is small enough not to need a
sub-package.
"""

from backend.core.exceptions import InsightPilotError


class ToolError(InsightPilotError):
    """Base class for every Tool Layer exception."""

    status_code = 500
    error_type = "ToolError"


class ToolNotFoundError(ToolError):
    """Raised when a tool is looked up in the ToolRegistry by an unregistered name."""

    status_code = 404
    error_type = "ToolNotFoundError"
