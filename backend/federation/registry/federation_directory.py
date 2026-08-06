"""FederationDirectory: capability-indexed lookups over the cluster fleet.

Deliberately never filters a *remote* cluster's advertised capabilities
against this process's own local registries — unlike
``backend.distributed.registry.capability_registry.DistributedCapabilityRegistry``
(Phase 38), which validates workers of the *same* process against the
*same* process's own real agents (correct, since a worker executes
in-process here), a remote cluster in a genuinely federated deployment
may legitimately support agents/plugins this process has never heard of.
This class only answers "given these requirements, which *registered*
clusters claim to satisfy them" — a pure query over already-declared
capabilities, never a validity check against local truth.
"""

from backend.federation.models.cluster import Cluster
from backend.federation.models.cluster_status import ClusterStatus
from backend.federation.registry.cluster_registry import ClusterRegistry

_ELIGIBLE_STATUSES = frozenset({ClusterStatus.ONLINE, ClusterStatus.DEGRADED})


class FederationDirectory:
    """Answers "which clusters can serve this requirement" queries over the fleet."""

    def __init__(self, cluster_registry: ClusterRegistry) -> None:
        self._cluster_registry = cluster_registry

    def clusters_supporting_agent(self, node_name: str) -> list[Cluster]:
        """Every cluster that advertises ``node_name`` as a supported agent."""
        return [cluster for cluster in self._cluster_registry.list_all() if cluster.supports_agent(node_name)]

    def clusters_supporting_plugin(self, plugin_id: str) -> list[Cluster]:
        """Every cluster that advertises ``plugin_id`` as a supported plugin."""
        return [
            cluster for cluster in self._cluster_registry.list_all()
            if plugin_id in cluster.capabilities.supported_plugins
        ]

    def clusters_supporting_mcp_adapter(self, adapter_id: str) -> list[Cluster]:
        """Every cluster that advertises ``adapter_id`` as a supported MCP adapter."""
        return [
            cluster for cluster in self._cluster_registry.list_all()
            if adapter_id in cluster.capabilities.supported_mcp_adapters
        ]

    def eligible_clusters(self, required_agents: list[str], step_count: int) -> list[Cluster]:
        """Every ONLINE/DEGRADED cluster with capacity that supports every required agent
        and whose own workflow-size limit accommodates ``step_count`` steps."""
        return [
            cluster
            for cluster in self._cluster_registry.list_all()
            if cluster.status in _ELIGIBLE_STATUSES
            and cluster.has_capacity()
            and cluster.supports_workflow_size(step_count)
            and all(cluster.supports_agent(name) for name in required_agents)
        ]
