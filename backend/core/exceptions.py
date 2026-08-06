"""Custom application exceptions.

Every exception here carries enough structure (an HTTP status code, a
machine-readable error type, and optional detail) for the global exception
handlers to convert it into the unified API response envelope without any
per-exception special-casing.
"""

from typing import Any


class InsightPilotError(Exception):
    """Base class for all InsightPilot application exceptions."""

    status_code: int = 500
    error_type: str = "InsightPilotError"

    def __init__(self, message: str, detail: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class NotFoundError(InsightPilotError):
    """Raised when a requested resource does not exist."""

    status_code = 404
    error_type = "NotFoundError"


class ValidationError(InsightPilotError):
    """Raised when input fails a business-rule validation (not schema validation)."""

    status_code = 422
    error_type = "ValidationError"


class StorageError(InsightPilotError):
    """Raised when a storage operation (path computation, filesystem access) fails."""

    status_code = 500
    error_type = "StorageError"


class ConfigurationError(InsightPilotError):
    """Raised when the application is misconfigured in a way that must not run."""

    status_code = 500
    error_type = "ConfigurationError"
