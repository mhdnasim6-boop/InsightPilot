"""Orchestration-layer exceptions."""

from backend.core.exceptions import InsightPilotError


class OrchestrationError(InsightPilotError):
    """Base class for all orchestration-layer exceptions."""

    status_code = 500
    error_type = "OrchestrationError"


class GraphValidationError(OrchestrationError):
    """Raised when a graph is malformed (missing entry point, dangling edge, ...)."""

    status_code = 500
    error_type = "GraphValidationError"


class CheckpointNotConfiguredError(OrchestrationError):
    """Raised when an operation requires a CheckpointInterface implementation that isn't configured."""

    status_code = 501
    error_type = "CheckpointNotConfiguredError"
