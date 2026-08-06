"""MCPService: the only entry point for the MCP layer.

Manages the registry, manages per-server client connections, and routes
tool requests to whichever ``MCPClient`` is attached — never the registry
or a client directly. No concrete ``MCPClient`` is attached to anything
by default: a future real implementation plugs in purely by calling
``attach_client()`` for an already-registered server, with no change to
this class, the registry, or the REST layer.
"""

from typing import Any

from backend.mcp.client.base import MCPClient
from backend.mcp.exceptions.errors import (
    MCPClientNotAvailableError,
    MCPConnectionFailedError,
    MCPServerNotConnectedError,
)
from backend.mcp.lifecycle.status import MCPConnectionStatus
from backend.mcp.models.capability import MCPCapability
from backend.mcp.models.health_summary import MCPHealthSummary
from backend.mcp.models.server import MCPServerDefinition
from backend.mcp.protocol.health import MCPHealthStatus
from backend.mcp.protocol.result import MCPToolResult
from backend.mcp.protocol.tool import MCPTool
from backend.mcp.registry.server_registry import MCPServerRegistry


class MCPService:
    """Manages MCP server registration, connections, and tool routing."""

    def __init__(self, registry: MCPServerRegistry) -> None:
        self._registry = registry
        self._clients: dict[str, MCPClient] = {}

    # -- Registry management ---------------------------------------------------

    def register_server(self, definition: MCPServerDefinition) -> MCPServerDefinition:
        """Register a new server. Raises MCPServerAlreadyRegisteredError if the id is taken."""
        return self._registry.register(definition)

    def unregister_server(self, server_id: str) -> bool:
        """Remove a registered server (and detach any client bound to it). Returns True if it existed."""
        self._clients.pop(server_id, None)
        return self._registry.unregister(server_id)

    def get_server(self, server_id: str) -> MCPServerDefinition:
        """Fetch one registered server. Raises MCPServerNotFoundError if unknown."""
        return self._registry.get(server_id)

    def list_servers(self) -> list[MCPServerDefinition]:
        """Return every registered server."""
        return self._registry.list()

    def list_servers_by_capability(self, capability: MCPCapability) -> list[MCPServerDefinition]:
        """Return every registered server that advertises the given capability."""
        return self._registry.list_by_capability(capability)

    def health_summary(self) -> MCPHealthSummary:
        """Aggregate how many registered servers are in each lifecycle state."""
        return self._registry.health_summary()

    # -- Connection management ---------------------------------------------------

    def attach_client(self, server_id: str, client: MCPClient) -> None:
        """Bind a real MCPClient implementation to an already-registered server.

        The one seam a future real transport implementation uses to plug
        in — everything else in this class, the registry, and the REST
        layer stays unchanged when a real client arrives.
        """
        self._registry.get(server_id)  # raises MCPServerNotFoundError if unknown
        self._clients[server_id] = client

    def detach_client(self, server_id: str) -> None:
        """Unbind whatever client is attached to a server, if any."""
        self._clients.pop(server_id, None)

    async def connect(self, server_id: str) -> MCPServerDefinition:
        """Connect to a server through its attached client.

        Raises MCPClientNotAvailableError if none is attached, or
        MCPConnectionFailedError (leaving the server FAILED) if the
        client's own connect() raises.
        """
        client = self._require_client(server_id)
        self._registry.update_status(server_id, MCPConnectionStatus.STARTING)
        try:
            await client.connect()
        except Exception as exc:
            self._registry.update_status(server_id, MCPConnectionStatus.FAILED)
            raise MCPConnectionFailedError(f"Failed to connect to server '{server_id}': {exc}") from exc
        return self._registry.update_status(server_id, MCPConnectionStatus.CONNECTED)

    async def disconnect(self, server_id: str) -> MCPServerDefinition:
        """Disconnect from a server through its attached client."""
        client = self._require_client(server_id)
        self._registry.update_status(server_id, MCPConnectionStatus.STOPPING)
        await client.disconnect()
        return self._registry.update_status(server_id, MCPConnectionStatus.DISCONNECTED)

    # -- Tool routing ---------------------------------------------------------

    async def list_tools(self, server_id: str) -> list[MCPTool]:
        """List the tools a connected server exposes. Raises MCPServerNotConnectedError otherwise."""
        client = self._require_connected_client(server_id)
        return await client.list_tools()

    async def invoke_tool(self, server_id: str, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Route a tool call to a connected server and return its structured result."""
        client = self._require_connected_client(server_id)
        return await client.invoke(tool_name, arguments)

    async def check_health(self, server_id: str) -> MCPHealthStatus:
        """Ask a server's attached client for a live health check."""
        client = self._require_client(server_id)
        return await client.health()

    # -- Internal helpers ---------------------------------------------------------

    def _require_client(self, server_id: str) -> MCPClient:
        self._registry.get(server_id)
        client = self._clients.get(server_id)
        if client is None:
            raise MCPClientNotAvailableError(f"No MCP client implementation is attached for server '{server_id}'.")
        return client

    def _require_connected_client(self, server_id: str) -> MCPClient:
        definition = self._registry.get(server_id)
        if definition.status != MCPConnectionStatus.CONNECTED:
            raise MCPServerNotConnectedError(
                f"Server '{server_id}' is not connected (status: {definition.status.value})."
            )
        return self._require_client(server_id)
