"""Observability framework exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing. A flat module, not a package — mirrors
``backend.tools.exceptions``/``backend.approval.exceptions``: this
phase's own error surface (trace lookup) is small enough not to need a
sub-package.
"""

from backend.core.exceptions import InsightPilotError


class ObservabilityError(InsightPilotError):
    """Base class for every observability-framework exception."""

    status_code = 500
    error_type = "ObservabilityError"


class TraceNotFoundError(ObservabilityError):
    """Raised when a trace is looked up by an unregistered trace_id."""

    status_code = 404
    error_type = "TraceNotFoundError"


class UnsupportedExportFormatError(ObservabilityError):
    """Raised when a trace export is requested in a format no exporter supports."""

    status_code = 400
    error_type = "UnsupportedExportFormatError"
