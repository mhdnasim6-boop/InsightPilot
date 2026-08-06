"""MCP exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing.
"""

from backend.core.exceptions import InsightPilotError


class MCPError(InsightPilotError):
    """Base class for every MCP-related exception."""

    status_code = 500
    error_type = "MCPError"


class MCPServerNotFoundError(MCPError):
    """Raised when a requested server_id isn't in the MCPServerRegistry."""

    status_code = 404
    error_type = "MCPServerNotFoundError"


class MCPServerAlreadyRegisteredError(MCPError):
    """Raised when registering a server_id that's already registered.

    Registration is deliberately not an upsert: two distinct servers
    colliding on the same id is far more likely to be a caller bug than
    an intentional replacement — unregister first, then register again.
    """

    status_code = 409
    error_type = "MCPServerAlreadyRegisteredError"


class InvalidLifecycleTransitionError(MCPError):
    """Raised when a server's status would jump between two states with no valid path."""

    status_code = 409
    error_type = "InvalidLifecycleTransitionError"


class MCPClientNotAvailableError(MCPError):
    """Raised when an operation needs a live MCPClient but none is attached.

    Expected, honest behavior in this phase: no real MCPClient
    implementation exists anywhere yet, so every connect/invoke call
    against a registered-but-unattached server raises this.
    """

    status_code = 503
    error_type = "MCPClientNotAvailableError"


class MCPServerNotConnectedError(MCPError):
    """Raised when routing a tool request to a server that isn't CONNECTED."""

    status_code = 409
    error_type = "MCPServerNotConnectedError"


class MCPConnectionFailedError(MCPError):
    """Raised when a client's connect() attempt fails."""

    status_code = 502
    error_type = "MCPConnectionFailedError"
