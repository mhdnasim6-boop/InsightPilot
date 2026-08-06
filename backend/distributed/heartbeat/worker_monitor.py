"""WorkerMonitor: detects workers whose heartbeat has gone stale.

No background timer/thread — this codebase has no precedent for a
recurring background task (``backend.core.job_manager.JobManager`` only
runs one-off jobs on demand), so staleness is checked lazily, on access:
``DistributedExecutionService`` calls ``sweep()`` at the start of its own
read/heartbeat methods (mirrors how this same codebase already treats
"is anything stale" as a query answered fresh on demand rather than a
ticking clock). A worker already OFFLINE/FAILED is left alone — sweeping
only ever moves a worker *into* OFFLINE, never out of it (only a fresh
heartbeat or explicit re-registration does that).
"""

from datetime import datetime

from backend.distributed.models.worker import Worker
from backend.distributed.models.worker_status import WorkerStatus
from backend.distributed.registry.worker_registry import WorkerRegistry
from backend.utils.time import utc_now

DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 90.0

_MONITORED_STATUSES = frozenset({WorkerStatus.ONLINE, WorkerStatus.BUSY, WorkerStatus.DRAINING})


class WorkerMonitor:
    """Marks workers OFFLINE once their heartbeat has gone silent for too long."""

    def __init__(self, worker_registry: WorkerRegistry, timeout_seconds: float = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS) -> None:
        self._worker_registry = worker_registry
        self._timeout_seconds = timeout_seconds

    def sweep(self, now: datetime | None = None) -> list[Worker]:
        """Mark every stale worker OFFLINE and return the ones just transitioned."""
        as_of = now or utc_now()
        newly_offline = []
        for worker in self._worker_registry.list_all():
            if worker.status not in _MONITORED_STATUSES:
                continue
            if worker.last_heartbeat is None or self._is_stale(worker.last_heartbeat, as_of):
                newly_offline.append(self._worker_registry.set_status(worker.worker_id, WorkerStatus.OFFLINE))
        return newly_offline

    def _is_stale(self, last_heartbeat: datetime, now: datetime) -> bool:
        return (now - last_heartbeat).total_seconds() > self._timeout_seconds
