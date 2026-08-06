"""AI-infrastructure exception hierarchy."""

from backend.core.exceptions import InsightPilotError


class AIError(InsightPilotError):
    """Base class for all AI-infrastructure exceptions."""

    status_code = 500
    error_type = "AIError"


class ProviderNotFoundError(AIError):
    """Raised when a requested provider name has no registered implementation."""

    status_code = 404
    error_type = "ProviderNotFoundError"


class ProviderConfigurationError(AIError):
    """Raised when a provider is misconfigured or unavailable by configuration."""

    status_code = 500
    error_type = "ProviderConfigurationError"


class ProviderTimeoutError(AIError):
    """Raised when a provider call exceeds its configured timeout."""

    status_code = 504
    error_type = "ProviderTimeoutError"


class ProviderAuthenticationError(AIError):
    """Raised when a provider rejects the configured credentials."""

    status_code = 401
    error_type = "ProviderAuthenticationError"


class InvalidPromptError(AIError):
    """Raised for an unregistered prompt name or a missing template variable."""

    status_code = 400
    error_type = "InvalidPromptError"


class StreamingError(AIError):
    """Raised when a streamed generation fails mid-stream."""

    status_code = 500
    error_type = "StreamingError"
