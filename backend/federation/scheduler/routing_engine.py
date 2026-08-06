"""RoutingEngine: a pure strategy over an already-eligible set of clusters.

Deliberately knows nothing about capabilities or status —
``ClusterSelector``/``FederationDirectory`` filter down to the eligible
candidate set first; this class only answers "given these candidates,
which one should get the next workload." Least-loaded by
``load_ratio()``, tie-broken by ``cluster_id`` for deterministic,
testable behavior — mirrors
``backend.distributed.scheduler.load_balancer.LoadBalancer`` exactly,
one layer up (Phase 38).
"""

from backend.federation.models.cluster import Cluster


class RoutingEngine:
    """Picks the least-loaded cluster among a set of candidates."""

    def select(self, candidates: list[Cluster]) -> Cluster | None:
        """Return the least-loaded candidate, or None if ``candidates`` is empty."""
        if not candidates:
            return None
        return min(candidates, key=lambda cluster: (cluster.load_ratio(), cluster.cluster_id))
