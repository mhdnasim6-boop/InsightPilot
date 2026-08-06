"""Cleaning-layer exception hierarchy."""

from backend.core.exceptions import InsightPilotError


class CleaningError(InsightPilotError):
    """Base class for all cleaning-layer exceptions."""

    status_code = 500
    error_type = "CleaningError"


class DataFrameNotFoundError(CleaningError):
    """Raised when a dataset has no resolvable DataFrame to clean."""

    status_code = 404
    error_type = "DataFrameNotFoundError"
