"""Abstract MCP client: the contract every future real transport implementation satisfies.

Unlike ``backend.ai.providers.base.AIProvider`` (which has ``MockProvider``)
or ``backend.datasource.sql.connectors.base.SQLConnector`` (which has 3 real
dialects), this ABC has zero concrete implementations anywhere in this
package — by design, per this phase's explicit scope. Every method is
abstract; there is no shared logic to provide yet because no transport
(stdio/http/websocket) is implemented. ``MCPService`` depends only on
this interface, never a concrete transport, so a future
``StdioMCPClient``/``HTTPMCPClient``/``WebSocketMCPClient`` plugs in
without any change to ``MCPService`` or the registry.
"""

from abc import ABC, abstractmethod
from typing import Any

from backend.mcp.protocol.health import MCPHealthStatus
from backend.mcp.protocol.result import MCPToolResult
from backend.mcp.protocol.tool import MCPTool


class MCPClient(ABC):
    """Contract every MCP client (any transport) must satisfy."""

    server_id: str

    @abstractmethod
    async def connect(self) -> None:
        """Establish a connection to this client's server."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection to this client's server."""

    @abstractmethod
    async def health(self) -> MCPHealthStatus:
        """Report whether this server is currently reachable and usable."""

    @abstractmethod
    async def list_tools(self) -> list[MCPTool]:
        """List every tool this server currently exposes."""

    @abstractmethod
    async def invoke(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Call one tool by name with the given arguments and return its structured result."""
