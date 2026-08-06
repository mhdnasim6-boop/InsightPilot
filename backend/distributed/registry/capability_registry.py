"""DistributedCapabilityRegistry: validates a worker's advertised capabilities
against the real, live set of known agent node names.

Reuses ``AgentCapabilityRegistry`` (Phase 30) directly — the exact same
mechanism ``WorkflowDispatcher`` (Phase 36) and the real Planner Agent
already use — rather than a second, hardcoded list of valid node names.
A worker advertising a capability this registry doesn't recognize is not
rejected outright (a future plugin agent may register a node before this
process's own ``GraphBuilder`` picks it up, or vice versa); it is simply
excluded from ``recognized_capabilities()``, so ``WorkerSelector`` never
routes real dispatch to a capability nothing in this process can execute.
"""

from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)


class DistributedCapabilityRegistry:
    """Answers "is this a real, dispatchable agent capability right now" — live, never hardcoded."""

    def __init__(self, agent_capability_registry: AgentCapabilityRegistry) -> None:
        self._agent_capability_registry = agent_capability_registry

    def known_node_names(self) -> set[str]:
        """Every node_name currently recognized as a real, registered agent."""
        return {capability.name for capability in self._agent_capability_registry.discover()}

    def is_recognized(self, node_name: str) -> bool:
        """Whether ``node_name`` corresponds to a real, currently registered agent."""
        return node_name in self.known_node_names()

    def recognized_capabilities(self, capabilities: list[str]) -> list[str]:
        """Filter ``capabilities`` down to only the ones this process can actually dispatch."""
        known = self.known_node_names()
        return [name for name in capabilities if name in known]
