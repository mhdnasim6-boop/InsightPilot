"""Analysis-layer exception hierarchy."""

from backend.core.exceptions import InsightPilotError


class AnalysisError(InsightPilotError):
    """Base class for all analysis-layer exceptions."""

    status_code = 500
    error_type = "AnalysisError"


class DataFrameNotFoundError(AnalysisError):
    """Raised when a dataset has no resolvable DataFrame to analyze."""

    status_code = 404
    error_type = "DataFrameNotFoundError"


class UnknownKPITypeError(AnalysisError):
    """Raised when a KPIDefinition references a kpi_type with no registered calculator."""

    status_code = 400
    error_type = "UnknownKPITypeError"
