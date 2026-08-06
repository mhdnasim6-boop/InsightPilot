"""MCPServerDefinition: the registry's own record of one MCP server.

Caller-provided metadata, not a live connection — registering one never
attempts to reach it. ``server_id`` is caller-supplied (a server's own
stable identity, e.g. ``"filesystem-local"``), not generated here, since
InsightPilot doesn't own the servers it registers.
"""

from typing import Any

from pydantic import BaseModel, Field

from backend.mcp.lifecycle.status import MCPConnectionStatus
from backend.mcp.models.capability import MCPCapability
from backend.mcp.transport.transport_type import MCPTransportType


class MCPServerDefinition(BaseModel):
    """A registered MCP server's identity, transport, capabilities, and current status."""

    server_id: str
    name: str
    description: str | None = None
    transport: MCPTransportType
    status: MCPConnectionStatus = MCPConnectionStatus.DISCONNECTED
    capabilities: list[MCPCapability] = Field(default_factory=list)
    version: str = "1.0.0"
    metadata: dict[str, Any] = Field(default_factory=dict)
