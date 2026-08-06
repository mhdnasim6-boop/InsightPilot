"""ToolRegistry: process-wide, name-keyed registry of every available Tool.

Dynamic registration only — this class never enumerates tool names
itself. Tools register themselves via DI wiring
(``backend.dependencies.tools``), the same way ``GraphBuilder`` never
hardcodes which orchestration nodes exist; adding a new tool never
requires touching this file.
"""

from typing import Any

from backend.tools.base.tool import Tool
from backend.tools.exceptions import ToolNotFoundError


class ToolRegistry:
    """Name -> Tool registry. The only place anything should look up a tool by name."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool[Any, Any]] = {}

    def register(self, tool: Tool[Any, Any]) -> None:
        """Register (or overwrite) a tool under its own ``name``."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Remove a tool by name, if registered. A no-op if it wasn't.

        Purely additive (Phase 33 — ``backend.plugins``): lets a plugin's
        contributed tools be cleanly removed on unload, without changing
        anything about how ``register()``/``get()``/``list_tools()``
        already behave for every existing caller.
        """
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool[Any, Any]:
        """Return a registered tool. Raises ToolNotFoundError if unknown."""
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(f"No tool registered under the name '{name}'.")
        return tool

    def list_tools(self) -> list[Tool[Any, Any]]:
        """Every registered tool, in registration order."""
        return list(self._tools.values())

    def list_metadata(self) -> list[dict[str, Any]]:
        """Every registered tool's self-description — the same shape a future MCP tool listing would expose."""
        return [tool.metadata() for tool in self._tools.values()]
