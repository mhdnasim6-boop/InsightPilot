"""HeartbeatManager: records heartbeats, renews leases, keeps a short history.

A heartbeat does two things at once, always together: it proves the
worker is alive (``WorkerRegistry.record_heartbeat()``) and it renews
every lease that worker currently holds (``LeaseManager.renew_all_for_worker()``)
— a worker that's still heartbeating should never have its in-flight
work reclaimed out from under it. Only a short, bounded history is kept
per worker (mirrors ``TraceStore``'s own "no unbounded growth" discipline)
— enough for a simple latency/freshness view, not a full audit log.
"""

from datetime import datetime

from backend.distributed.models.worker import Worker
from backend.distributed.models.worker_heartbeat import WorkerHeartbeat
from backend.distributed.registry.worker_registry import WorkerRegistry
from backend.distributed.scheduler.lease_manager import LeaseManager
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

MAX_HISTORY_PER_WORKER = 20


class HeartbeatManager:
    """Records worker heartbeats and renews their outstanding leases."""

    def __init__(self, worker_registry: WorkerRegistry, lease_manager: LeaseManager) -> None:
        self._worker_registry = worker_registry
        self._lease_manager = lease_manager
        self._history: dict[str, list[WorkerHeartbeat]] = {}

    def record(
        self, worker_id: str, active_task_count: int | None = None, metadata: dict | None = None
    ) -> tuple[Worker, WorkerHeartbeat]:
        """Record one heartbeat: refresh the worker, renew its leases, and keep a short history."""
        now = utc_now()
        worker = self._worker_registry.record_heartbeat(worker_id, now)
        self._lease_manager.renew_all_for_worker(worker_id, now)

        heartbeat = WorkerHeartbeat(
            heartbeat_id=generate_id(),
            worker_id=worker_id,
            received_at=now,
            active_task_count=active_task_count if active_task_count is not None else len(worker.active_tasks),
            metadata=metadata or {},
        )
        history = [*self._history.get(worker_id, []), heartbeat][-MAX_HISTORY_PER_WORKER:]
        self._history[worker_id] = history
        return worker, heartbeat

    def history_for(self, worker_id: str) -> list[WorkerHeartbeat]:
        """Every retained heartbeat for ``worker_id``, oldest first."""
        return list(self._history.get(worker_id, []))

    def latency_seconds(self, worker: Worker, now: datetime | None = None) -> float | None:
        """How long ago ``worker``'s last heartbeat was received, or None if it never has."""
        if worker.last_heartbeat is None:
            return None
        return ((now or utc_now()) - worker.last_heartbeat).total_seconds()
