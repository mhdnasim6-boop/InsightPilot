"""ClusterRegistry: the process-wide store of every registered Cluster.

Mirrors ``WorkerRegistry``'s own exact shape (Phase 38) one layer up.
``register()`` is idempotent by ``cluster_id`` — a cluster re-registering
(the same idempotent-register-as-liveness-proof pattern Phase 38 used
for workers, since there is no separate heartbeat endpoint for clusters —
see ``HealthMonitor``'s own docstring for why) is a normal event, not an
error: it refreshes ``last_seen`` and revives an OFFLINE/DEGRADED cluster
back to ONLINE.
"""

from datetime import datetime
from typing import Any

from backend.federation.exceptions import ClusterNotFoundError
from backend.federation.models.cluster import Cluster
from backend.federation.models.cluster_capability import ClusterCapability
from backend.federation.models.cluster_status import ClusterStatus
from backend.utils.time import utc_now


class ClusterRegistry:
    """CRUD + lifecycle transitions over the process-wide cluster fleet."""

    def __init__(self) -> None:
        self._clusters: dict[str, Cluster] = {}

    def register(
        self,
        cluster_id: str,
        name: str,
        endpoint: str,
        capabilities: ClusterCapability,
        version: str = "0.1.0",
        registered_workers: int = 0,
        metadata: dict[str, Any] | None = None,
        is_local: bool = False,
    ) -> Cluster:
        """Register (or re-register) a cluster. Idempotent by cluster_id."""
        now = utc_now()
        existing = self._clusters.get(cluster_id)
        cluster = Cluster(
            cluster_id=cluster_id,
            name=name,
            endpoint=endpoint,
            status=ClusterStatus.ONLINE,
            version=version,
            capabilities=capabilities,
            registered_workers=registered_workers,
            active_remote_executions=list(existing.active_remote_executions) if existing else [],
            metadata=metadata or {},
            is_local=is_local,
            registered_at=existing.registered_at if existing else now,
            last_seen=now,
        )
        self._clusters[cluster_id] = cluster
        return cluster

    def get(self, cluster_id: str) -> Cluster:
        """Fetch a cluster. Raises ClusterNotFoundError if unknown."""
        cluster = self._clusters.get(cluster_id)
        if cluster is None:
            raise ClusterNotFoundError(f"No cluster found for '{cluster_id}'.")
        return cluster

    def list_all(self) -> list[Cluster]:
        """Every registered cluster, in registration order."""
        return list(self._clusters.values())

    def list_by_status(self, status: ClusterStatus) -> list[Cluster]:
        """Every cluster currently in the given status."""
        return [cluster for cluster in self._clusters.values() if cluster.status == status]

    def put(self, cluster: Cluster) -> Cluster:
        """Store (overwrite) a cluster snapshot, keyed by its own cluster_id."""
        self._clusters[cluster.cluster_id] = cluster
        return cluster

    def set_status(self, cluster_id: str, status: ClusterStatus, health_score: float | None = None) -> Cluster:
        """Transition a cluster to a new status (and, optionally, a fresh health score)."""
        update: dict[str, Any] = {"status": status}
        if health_score is not None:
            update["health_score"] = health_score
        return self.put(self.get(cluster_id).model_copy(update=update))

    def touch(self, cluster_id: str, now: datetime | None = None) -> Cluster:
        """Refresh a cluster's last_seen, and revive an OFFLINE/DEGRADED cluster to ONLINE."""
        cluster = self.get(cluster_id)
        update: dict[str, Any] = {"last_seen": now or utc_now(), "health_score": 1.0}
        if cluster.status in {ClusterStatus.OFFLINE, ClusterStatus.DEGRADED}:
            update["status"] = ClusterStatus.ONLINE
        return self.put(cluster.model_copy(update=update))

    def add_active_execution(self, cluster_id: str, remote_execution_id: str) -> Cluster:
        """Credit one more active remote execution to a cluster."""
        cluster = self.get(cluster_id)
        active = [*cluster.active_remote_executions, remote_execution_id]
        return self.put(cluster.model_copy(update={"active_remote_executions": active}))

    def remove_active_execution(self, cluster_id: str, remote_execution_id: str) -> Cluster:
        """Release one active remote execution from a cluster."""
        cluster = self.get(cluster_id)
        active = [rid for rid in cluster.active_remote_executions if rid != remote_execution_id]
        return self.put(cluster.model_copy(update={"active_remote_executions": active}))

    def remove(self, cluster_id: str) -> None:
        """Deregister a cluster entirely. A no-op if already absent."""
        self._clusters.pop(cluster_id, None)
