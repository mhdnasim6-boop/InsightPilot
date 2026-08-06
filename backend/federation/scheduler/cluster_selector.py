"""ClusterSelector: which cluster, if any, should receive a workload.

Composes ``FederationDirectory`` (who's eligible) and ``RoutingEngine``
(which eligible one) — mirrors
``backend.distributed.scheduler.worker_selector.WorkerSelector`` exactly,
one layer up. Returns ``None`` — never raises — when nothing is
eligible; the local cluster (registered by ``FederationService`` itself)
is always one of the candidates, so in the common single-cluster
deployment this always resolves to "local," exactly reproducing Phase
38's own behavior with zero remote clusters registered.
"""

from backend.federation.models.cluster import Cluster
from backend.federation.registry.federation_directory import FederationDirectory
from backend.federation.scheduler.routing_engine import RoutingEngine


class ClusterSelector:
    """Selects one eligible, least-loaded cluster for a given workload requirement."""

    def __init__(self, directory: FederationDirectory, routing_engine: RoutingEngine) -> None:
        self._directory = directory
        self._routing_engine = routing_engine

    def select_for(self, required_agents: list[str], step_count: int, exclude: set[str] | None = None) -> Cluster | None:
        """Return the best eligible cluster for this workload, or None if nothing qualifies."""
        candidates = self._directory.eligible_clusters(required_agents, step_count)
        if exclude:
            candidates = [cluster for cluster in candidates if cluster.cluster_id not in exclude]
        return self._routing_engine.select(candidates)
