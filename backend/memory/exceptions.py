"""Memory layer exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing — mirrors ``backend.observability.exceptions``/
``backend.execution.exceptions.errors``. A flat module, not a package:
this phase's own error surface (item lookup) is small enough not to
need one.
"""

from backend.core.exceptions import InsightPilotError


class MemoryError(InsightPilotError):
    """Base class for every memory-layer exception."""

    status_code = 500
    error_type = "MemoryError"


class MemoryItemNotFoundError(MemoryError):
    """Raised when a memory is looked up by an unregistered memory_id."""

    status_code = 404
    error_type = "MemoryItemNotFoundError"
