"""Report generation exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing.
"""

from backend.core.exceptions import InsightPilotError


class ReportError(InsightPilotError):
    """Base class for all report generation exceptions."""

    status_code = 500
    error_type = "ReportError"


class UnknownReportTemplateError(ReportError):
    """Raised for a report template type with no registered configuration.

    Should never happen in practice — ``ReportTemplateType`` is a closed
    enum and every member is registered — a defensive guard only.
    """

    status_code = 400
    error_type = "UnknownReportTemplateError"


class ReportNotFoundError(ReportError):
    """Raised when a requested report_id doesn't exist in the ReportStore."""

    status_code = 404
    error_type = "ReportNotFoundError"


class ReportValidationFailedError(ReportError):
    """Raised when a generated report fails structural validation.

    Always carries the triggering ``ReportValidationResult`` as ``detail``.
    """

    status_code = 422
    error_type = "ReportValidationFailedError"


class UnknownExportFormatError(ReportError):
    """Raised for an export format with no registered exporter.

    Should never happen — ``ReportExportFormat`` is a closed enum and
    every member has an exporter (real or placeholder) registered.
    """

    status_code = 400
    error_type = "UnknownExportFormatError"


class UnknownReportThemeError(ReportError):
    """Raised when a requested report theme name isn't registered."""

    status_code = 404
    error_type = "UnknownReportThemeError"
