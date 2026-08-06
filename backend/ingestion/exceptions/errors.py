"""Ingestion-layer exception hierarchy."""

from backend.core.exceptions import InsightPilotError


class IngestionError(InsightPilotError):
    """Base class for all ingestion-layer exceptions."""

    status_code = 500
    error_type = "IngestionError"


class UnsupportedSourceError(IngestionError):
    """Raised for a file extension with no registered (or placeholder) loader."""

    status_code = 415
    error_type = "UnsupportedSourceError"


class SourceNotImplementedError(IngestionError):
    """Raised for a recognized source type (e.g. PDF) with no loader implementation yet."""

    status_code = 501
    error_type = "SourceNotImplementedError"


class DatasetCorruptedError(IngestionError):
    """Raised by a loader when a source file cannot be parsed at all."""

    status_code = 422
    error_type = "DatasetCorruptedError"


class DatasetValidationError(IngestionError):
    """Raised when a source or loaded dataset fails structured validation.

    Always carries the triggering ``DatasetValidationResult`` as ``detail``.
    """

    status_code = 422
    error_type = "DatasetValidationError"
