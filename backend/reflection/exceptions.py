"""Reflection exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing — mirrors ``backend.execution.exceptions``/
``backend.collaboration.exceptions``.
"""

from backend.core.exceptions import InsightPilotError


class ReflectionError(InsightPilotError):
    """Base class for every reflection-layer exception."""

    status_code = 500
    error_type = "ReflectionError"


class ReflectionNotFoundError(ReflectionError):
    """Raised when a reflection is looked up by an unregistered reflection_id."""

    status_code = 404
    error_type = "ReflectionNotFoundError"
