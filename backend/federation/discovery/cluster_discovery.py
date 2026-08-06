"""ClusterDiscovery: the explicit registration entry point.

"Cluster registration is explicit... no automatic networking" — this
class is the whole of "discovery" in this phase: it never scans a
network or calls a remote endpoint, it only records a registration a
caller (a real remote deployment, or an operator) explicitly submitted
over REST, delegating the actual state transition to ``ClusterRegistry``
and keeping a short, bounded audit history of every registration event
via ``ClusterRegistration`` — mirrors ``HeartbeatManager``'s own bounded
history precedent (Phase 38).
"""

from typing import Any

from backend.federation.models.cluster import Cluster
from backend.federation.models.cluster_capability import ClusterCapability
from backend.federation.models.cluster_registration import ClusterRegistration
from backend.federation.registry.cluster_registry import ClusterRegistry
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

MAX_HISTORY_PER_CLUSTER = 20


class ClusterDiscovery:
    """Records explicit cluster registrations and their short audit history."""

    def __init__(self, cluster_registry: ClusterRegistry) -> None:
        self._cluster_registry = cluster_registry
        self._history: dict[str, list[ClusterRegistration]] = {}

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
        """Register (or re-register) a cluster and record the registration event."""
        cluster = self._cluster_registry.register(
            cluster_id, name, endpoint, capabilities, version, registered_workers, metadata, is_local,
        )
        registration = ClusterRegistration(
            registration_id=generate_id(), cluster_id=cluster_id, name=name, endpoint=endpoint,
            registered_at=utc_now(), metadata=metadata or {},
        )
        history = [*self._history.get(cluster_id, []), registration][-MAX_HISTORY_PER_CLUSTER:]
        self._history[cluster_id] = history
        return cluster

    def history_for(self, cluster_id: str) -> list[ClusterRegistration]:
        """Every retained registration event for ``cluster_id``, oldest first."""
        return list(self._history.get(cluster_id, []))
