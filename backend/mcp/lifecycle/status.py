"""MCP server connection lifecycle: the 5 states a registered server moves through.

A plain state machine, not just an enum — ``can_transition()`` is what
lets ``MCPServerRegistry.update_status()`` reject an impossible jump
(e.g. ``DISCONNECTED`` straight to ``CONNECTED``, skipping ``STARTING``)
instead of silently accepting any value.
"""

from enum import Enum


class MCPConnectionStatus(str, Enum):
    """Lifecycle state of one registered MCP server."""

    DISCONNECTED = "disconnected"
    STARTING = "starting"
    CONNECTED = "connected"
    STOPPING = "stopping"
    FAILED = "failed"


_VALID_TRANSITIONS: dict[MCPConnectionStatus, frozenset[MCPConnectionStatus]] = {
    MCPConnectionStatus.DISCONNECTED: frozenset({MCPConnectionStatus.STARTING}),
    MCPConnectionStatus.STARTING: frozenset({MCPConnectionStatus.CONNECTED, MCPConnectionStatus.FAILED}),
    MCPConnectionStatus.CONNECTED: frozenset({MCPConnectionStatus.STOPPING, MCPConnectionStatus.FAILED}),
    MCPConnectionStatus.STOPPING: frozenset({MCPConnectionStatus.DISCONNECTED, MCPConnectionStatus.FAILED}),
    MCPConnectionStatus.FAILED: frozenset({MCPConnectionStatus.STARTING, MCPConnectionStatus.DISCONNECTED}),
}


def can_transition(current: MCPConnectionStatus, target: MCPConnectionStatus) -> bool:
    """Return whether ``current -> target`` is a valid lifecycle transition."""
    return target in _VALID_TRANSITIONS.get(current, frozenset())
