"""MCP exception hierarchy."""

from backend.mcp.exceptions.errors import (
    InvalidLifecycleTransitionError,
    MCPClientNotAvailableError,
    MCPConnectionFailedError,
    MCPError,
    MCPServerAlreadyRegisteredError,
    MCPServerNotConnectedError,
    MCPServerNotFoundError,
)

__all__ = [
    "InvalidLifecycleTransitionError",
    "MCPClientNotAvailableError",
    "MCPConnectionFailedError",
    "MCPError",
    "MCPServerAlreadyRegisteredError",
    "MCPServerNotConnectedError",
    "MCPServerNotFoundError",
]
