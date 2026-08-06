"""WorkerSelector: which worker, if any, should run a step needing ``node_name``.

Composes ``WorkerRegistry`` (who exists), ``DistributedCapabilityRegistry``
(is this capability even real), and ``LoadBalancer`` (which eligible one).
Returns ``None`` — never raises — when nothing is eligible: this phase is
purely additive, so a deployment with zero registered workers (every
existing test, and any real deployment that hasn't opted in yet) must
behave exactly as it did before this phase existed.
"""

from backend.distributed.models.worker import Worker
from backend.distributed.models.worker_status import WorkerStatus
from backend.distributed.registry.capability_registry import (
    DistributedCapabilityRegistry,
)
from backend.distributed.registry.worker_registry import WorkerRegistry
from backend.distributed.scheduler.load_balancer import LoadBalancer

_ELIGIBLE_STATUSES = frozenset({WorkerStatus.ONLINE, WorkerStatus.BUSY})


class WorkerSelector:
    """Selects one eligible, least-loaded worker for a given node_name."""

    def __init__(
        self,
        worker_registry: WorkerRegistry,
        capability_registry: DistributedCapabilityRegistry,
        load_balancer: LoadBalancer,
    ) -> None:
        self._worker_registry = worker_registry
        self._capability_registry = capability_registry
        self._load_balancer = load_balancer

    def select_for(self, node_name: str) -> Worker | None:
        """Return the best eligible worker for ``node_name``, or None if nothing qualifies."""
        if not self._capability_registry.is_recognized(node_name):
            return None
        candidates = [
            worker
            for worker in self._worker_registry.list_supporting(node_name)
            if worker.status in _ELIGIBLE_STATUSES and worker.has_capacity()
        ]
        return self._load_balancer.select(candidates)
