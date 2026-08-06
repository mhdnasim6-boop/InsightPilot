"""HealthMonitor: lazy, on-access staleness detection for the cluster fleet.

No background timer exists anywhere in this codebase
(``backend.core.job_manager.JobManager`` only runs one-off jobs, never a
recurring one — the same precedent ``backend.distributed.heartbeat.worker_monitor.WorkerMonitor``
already established in Phase 38) — so "periodic" health monitoring here
means ``sweep()`` runs fresh every time ``FederationService`` reads
cluster/health/statistics state, not a ticking clock. There is
deliberately no ``POST /clusters/heartbeat`` endpoint in this phase's own
REST surface — re-registration (``POST /clusters/register``, already
idempotent) is what proves a remote cluster is still alive, exactly like
Phase 38's own worker registration doubles as its own liveness proof.
The local cluster (``is_local``) is never swept — its own liveness is
this very process, never "did someone re-register me."
"""

from datetime import datetime

from backend.federation.models.cluster import Cluster
from backend.federation.models.cluster_status import ClusterStatus
from backend.federation.registry.cluster_registry import ClusterRegistry
from backend.utils.time import utc_now

DEFAULT_DEGRADED_AFTER_SECONDS = 60.0
DEFAULT_OFFLINE_AFTER_SECONDS = 180.0

_MONITORED_STATUSES = frozenset({ClusterStatus.ONLINE, ClusterStatus.DEGRADED})


class HealthMonitor:
    """Marks stale remote clusters DEGRADED, then OFFLINE, as their last_seen ages."""

    def __init__(
        self,
        cluster_registry: ClusterRegistry,
        degraded_after_seconds: float = DEFAULT_DEGRADED_AFTER_SECONDS,
        offline_after_seconds: float = DEFAULT_OFFLINE_AFTER_SECONDS,
    ) -> None:
        self._cluster_registry = cluster_registry
        self._degraded_after_seconds = degraded_after_seconds
        self._offline_after_seconds = offline_after_seconds

    def sweep(self, now: datetime | None = None) -> list[Cluster]:
        """Re-score every remote cluster's freshness, transitioning statuses as needed.
        Returns every cluster whose status or health_score actually changed."""
        as_of = now or utc_now()
        changed = []
        for cluster in self._cluster_registry.list_all():
            if cluster.is_local or cluster.status not in _MONITORED_STATUSES:
                continue
            updated = self._rescore(cluster, as_of)
            if updated.status != cluster.status or updated.health_score != cluster.health_score:
                changed.append(self._cluster_registry.put(updated))
        return changed

    def _rescore(self, cluster: Cluster, now: datetime) -> Cluster:
        last_seen = cluster.last_seen or cluster.registered_at
        if last_seen is None:
            return cluster
        age = (now - last_seen).total_seconds()

        if age > self._offline_after_seconds:
            return cluster.model_copy(update={"status": ClusterStatus.OFFLINE, "health_score": 0.0})
        if age > self._degraded_after_seconds:
            span = self._offline_after_seconds - self._degraded_after_seconds
            remaining = self._offline_after_seconds - age
            health_score = max(0.0, min(1.0, remaining / span)) if span > 0 else 0.0
            return cluster.model_copy(update={"status": ClusterStatus.DEGRADED, "health_score": health_score})

        freshness = max(0.0, min(1.0, 1.0 - (age / self._degraded_after_seconds))) if self._degraded_after_seconds > 0 else 1.0
        return cluster.model_copy(update={"status": ClusterStatus.ONLINE, "health_score": max(freshness, 0.5)})
