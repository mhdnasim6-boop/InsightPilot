"""In-memory registry of MCPServerDefinitions.

Mirrors ``backend.reporting.report_store.ReportStore`` in shape (a plain
dict keyed by id, no if/else chains anywhere), but ``register()`` refuses
to silently overwrite an existing id — two distinct servers colliding on
one server_id is far more likely a caller bug than an intentional
replacement, so the caller must ``unregister()`` first.
"""

from backend.mcp.exceptions.errors import (
    InvalidLifecycleTransitionError,
    MCPServerAlreadyRegisteredError,
    MCPServerNotFoundError,
)
from backend.mcp.lifecycle.status import MCPConnectionStatus, can_transition
from backend.mcp.models.capability import MCPCapability
from backend.mcp.models.health_summary import MCPHealthSummary
from backend.mcp.models.server import MCPServerDefinition


class MCPServerRegistry:
    """Process-wide registry of MCP servers, keyed by server_id."""

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerDefinition] = {}

    def register(self, definition: MCPServerDefinition) -> MCPServerDefinition:
        """Register a new server. Raises MCPServerAlreadyRegisteredError if the id is taken."""
        if definition.server_id in self._servers:
            raise MCPServerAlreadyRegisteredError(f"Server '{definition.server_id}' is already registered.")
        self._servers[definition.server_id] = definition
        return definition

    def unregister(self, server_id: str) -> bool:
        """Remove a registered server. Returns True if it existed."""
        return self._servers.pop(server_id, None) is not None

    def get(self, server_id: str) -> MCPServerDefinition:
        """Return the server registered under server_id. Raises MCPServerNotFoundError if unknown."""
        definition = self._servers.get(server_id)
        if definition is None:
            raise MCPServerNotFoundError(f"MCP server '{server_id}' is not registered.")
        return definition

    def list_by_capability(self, capability: MCPCapability) -> list[MCPServerDefinition]:
        """Return every registered server that advertises the given capability."""
        return [definition for definition in self._servers.values() if capability in definition.capabilities]

    def update_status(self, server_id: str, new_status: MCPConnectionStatus) -> MCPServerDefinition:
        """Move a server to a new lifecycle status.

        Raises MCPServerNotFoundError if unknown, or
        InvalidLifecycleTransitionError if the jump isn't a valid one.
        """
        definition = self.get(server_id)
        if not can_transition(definition.status, new_status):
            raise InvalidLifecycleTransitionError(
                f"Cannot transition server '{server_id}' from '{definition.status.value}' to '{new_status.value}'."
            )
        updated = definition.model_copy(update={"status": new_status})
        self._servers[server_id] = updated
        return updated

    def health_summary(self) -> MCPHealthSummary:
        """Aggregate how many registered servers are in each lifecycle state."""
        counts: dict[str, int] = {}
        for definition in self._servers.values():
            counts[definition.status.value] = counts.get(definition.status.value, 0) + 1
        return MCPHealthSummary(total_servers=len(self._servers), by_status=counts)

    def list(self) -> list[MCPServerDefinition]:
        """Return every registered server.

        Defined last in the class body deliberately: a method literally
        named ``list`` shadows the builtin ``list`` for every annotation
        that follows it within this class (verified empirically — it is
        a real ``TypeError`` at import time, not just a mypy nitpick), so
        every other method's ``list[...]`` return annotation must be
        resolved first.
        """
        return list(self._servers.values())
