"""FederationService: the ONLY public entry point for the federation layer.

Composes every collaborator in ``backend/federation/`` — registry,
directory, discovery, health, scheduler, failover — into one facade,
mirroring ``DistributedExecutionService``/``WorkflowService``'s own "one
object, everything goes through it" shape.

The local cluster (``LOCAL_CLUSTER_ID``) is seeded and refreshed by
``backend.dependencies.federation.ensure_local_cluster`` — a real
dependency of both this class's own DI provider
(``get_federation_service()``) and of ``get_federation_directory()`` (the
provider the ``FederationCoordinator``/``WorkloadRouter`` routing path
actually uses), so the local cluster is guaranteed to exist wherever
either path is used, always reflecting the real, live
``AgentCapabilityRegistry``/``PluginRegistry``/``MCPService``/
``DistributedExecutionService`` state at request time, never a stale
snapshot. This is what makes the single-cluster deployment case behave
identically to Phase 38: with zero *remote* clusters ever registered,
every workload's routing always resolves to this one, always-eligible
local cluster — a real decision, not a bypassed one, but one that never
changes where a step actually runs.
"""

from typing import Any

from backend.federation.coordination.cluster_allocator import ClusterAllocator
from backend.federation.discovery.cluster_discovery import ClusterDiscovery
from backend.federation.discovery.health_monitor import HealthMonitor
from backend.federation.exceptions import CannotRemoveLocalClusterError
from backend.federation.exporters.json_exporter import export_federation_json
from backend.federation.exporters.mermaid_exporter import export_federation_mermaid
from backend.federation.models.cluster import Cluster
from backend.federation.models.cluster_capability import ClusterCapability
from backend.federation.models.cluster_status import ClusterStatus
from backend.federation.models.federation_statistics import FederationStatistics
from backend.federation.models.routing_decision import RoutingDecision
from backend.federation.registry.cluster_registry import ClusterRegistry
from backend.federation.scheduler.federation_scheduler import FederationScheduler
from backend.utils.time import utc_now

LOCAL_CLUSTER_ID = "local"
LOCAL_CLUSTER_ENDPOINT = "local://in-process"


class FederationService:
    """Runs the full lifecycle of cluster registration, health, routing, and failover."""

    def __init__(
        self,
        cluster_registry: ClusterRegistry,
        cluster_discovery: ClusterDiscovery,
        health_monitor: HealthMonitor,
        federation_scheduler: FederationScheduler,
        cluster_allocator: ClusterAllocator,
    ) -> None:
        self._cluster_registry = cluster_registry
        self._cluster_discovery = cluster_discovery
        self._health_monitor = health_monitor
        self._federation_scheduler = federation_scheduler
        self._cluster_allocator = cluster_allocator

    # -- Cluster lifecycle ------------------------------------------------------------

    def register_cluster(
        self,
        cluster_id: str,
        name: str,
        endpoint: str,
        capabilities: ClusterCapability,
        version: str = "0.1.0",
        registered_workers: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Cluster:
        """Register (or re-register) a remote cluster. Idempotent by cluster_id."""
        return self._cluster_discovery.register(
            cluster_id, name, endpoint, capabilities, version, registered_workers, metadata, is_local=False,
        )

    def remove_cluster(self, cluster_id: str) -> None:
        """Deregister a remote cluster. Raises ClusterNotFoundError if unknown, or
        CannotRemoveLocalClusterError if asked to remove this process's own local cluster."""
        if cluster_id == LOCAL_CLUSTER_ID:
            raise CannotRemoveLocalClusterError("The local cluster cannot be removed.")
        self._cluster_registry.get(cluster_id)  # raises ClusterNotFoundError if unknown
        self._cluster_registry.remove(cluster_id)

    def get_cluster(self, cluster_id: str) -> Cluster:
        """Fetch one cluster by id, after a health sweep."""
        self._health_monitor.sweep()
        return self._cluster_registry.get(cluster_id)

    def list_clusters(self) -> list[Cluster]:
        """Every registered cluster (including the local one), after a health sweep."""
        self._health_monitor.sweep()
        return self._cluster_registry.list_all()

    # -- Health -------------------------------------------------------------------------

    def get_health(self) -> list[Cluster]:
        """Every cluster's current health snapshot, after a fresh sweep."""
        self._health_monitor.sweep()
        return self._cluster_registry.list_all()

    # -- Statistics / routing / export ---------------------------------------------------

    def federation_statistics(self) -> FederationStatistics:
        """Aggregate counts across the whole cluster fleet, after a health sweep."""
        self._health_monitor.sweep()
        clusters = self._cluster_registry.list_all()
        by_status = {status: len([c for c in clusters if c.status == status]) for status in ClusterStatus}
        return FederationStatistics(
            total_clusters=len(clusters),
            online_clusters=by_status[ClusterStatus.ONLINE],
            degraded_clusters=by_status[ClusterStatus.DEGRADED],
            offline_clusters=by_status[ClusterStatus.OFFLINE],
            maintenance_clusters=by_status[ClusterStatus.MAINTENANCE],
            failed_clusters=by_status[ClusterStatus.FAILED],
            total_registered_workers=sum(c.registered_workers for c in clusters),
            total_capacity=sum(c.capabilities.maximum_concurrent_executions for c in clusters),
            active_remote_executions=sum(len(c.active_remote_executions) for c in clusters),
            pending_routing_decisions=len(self._federation_scheduler.list_pending()),
            generated_at=utc_now(),
        )

    def list_routing_decisions(self) -> list[RoutingDecision]:
        """Every routing decision ever made, in creation order."""
        return self._federation_scheduler.list_all()

    def export_json(self) -> str:
        """Serialize the whole federation (clusters + routing decisions + statistics) as JSON."""
        return export_federation_json(self.list_clusters(), self.list_routing_decisions(), self.federation_statistics())

    def export_mermaid(self) -> str:
        """Render the cluster topology and active routing as a Mermaid flowchart."""
        return export_federation_mermaid(self.list_clusters(), self.list_routing_decisions())
