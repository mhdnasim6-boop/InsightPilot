"""Visualization-layer exception hierarchy."""

from backend.core.exceptions import InsightPilotError


class VisualizationError(InsightPilotError):
    """Base class for all visualization-layer exceptions."""

    status_code = 500
    error_type = "VisualizationError"


class UnknownChartTypeError(VisualizationError):
    """Raised when an exporter has no renderer registered for a chart's type."""

    status_code = 400
    error_type = "UnknownChartTypeError"


class UnknownThemeError(VisualizationError):
    """Raised when a requested theme name isn't registered."""

    status_code = 404
    error_type = "UnknownThemeError"
