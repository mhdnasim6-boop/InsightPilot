"""WorkflowDispatcher: dynamic agent/tool/plugin discovery — never a
hardcoded name.

Agents are discovered through ``AgentCapabilityRegistry`` (Phase 30),
itself already reading live from ``GraphBuilder`` — the exact same
source ``PlannerAgent`` and ``CollaborationService`` already use, so a
future sixth/seventh agent node needs zero changes here. Tools come from
the live ``ToolRegistry`` (Phase 22); plugin-contributed extensions
(including plugin-registered Tools) come from the live ``PluginRegistry``
(Phase 33). No new registry, no new discovery mechanism — this class
only composes the three that already exist.
"""

from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.collaboration.models.agent_capability import AgentCapability
from backend.plugins.lifecycle.lifecycle import PluginState
from backend.plugins.registry.plugin_registry import PluginRegistry
from backend.tools.registry.tool_registry import ToolRegistry


class WorkflowDispatcher:
    """Answers "what can a workflow step actually reference right now" — live, never hardcoded."""

    def __init__(
        self, capability_registry: AgentCapabilityRegistry, tool_registry: ToolRegistry, plugin_registry: PluginRegistry,
    ) -> None:
        self._capability_registry = capability_registry
        self._tool_registry = tool_registry
        self._plugin_registry = plugin_registry

    def discover_agents(self) -> list[AgentCapability]:
        """Every currently registered orchestration agent, discovered live from GraphBuilder."""
        return self._capability_registry.discover()

    def discover_agent_names(self) -> set[str]:
        """Just the names — what a WorkflowStep's own ``node_name`` is validated against."""
        return {capability.name for capability in self.discover_agents()}

    def discover_tools(self) -> list[str]:
        """Every currently registered tool's name, from the live ToolRegistry."""
        return [tool.name for tool in self._tool_registry.list_tools()]

    def discover_plugins(self) -> list[str]:
        """Every currently loaded (REGISTERED-state) plugin's id, from the live PluginRegistry."""
        return [record.manifest.id for record in self._plugin_registry.list() if record.state == PluginState.REGISTERED]

    def is_known_agent(self, node_name: str) -> bool:
        """Whether ``node_name`` names a real, currently discoverable agent."""
        return node_name in self.discover_agent_names()
