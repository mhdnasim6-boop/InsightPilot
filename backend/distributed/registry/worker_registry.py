"""WorkerRegistry: the process-wide store of every registered Worker.

Mirrors ``ApprovalStore``/``MemoryStore``'s own "plain dict, process-wide,
no persistence backend yet" convention. ``register()`` is idempotent by
``worker_id`` — a worker process restarting and registering again is a
normal, expected event (its own capabilities/capacity may have changed),
not an error, so this never raises on a repeat registration; it simply
resets that worker to ONLINE with a fresh ``last_heartbeat``.
"""

from datetime import datetime
from typing import Any

from backend.distributed.exceptions import WorkerNotFoundError
from backend.distributed.models.worker import Worker
from backend.distributed.models.worker_capability import WorkerCapability
from backend.distributed.models.worker_status import WorkerStatus
from backend.utils.time import utc_now


class WorkerRegistry:
    """CRUD + lifecycle transitions over the process-wide worker fleet."""

    def __init__(self) -> None:
        self._workers: dict[str, Worker] = {}

    def register(
        self,
        worker_id: str,
        hostname: str,
        capabilities: list[str],
        maximum_parallel_tasks: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> Worker:
        """Register (or re-register) a worker. Idempotent by worker_id."""
        now = utc_now()
        existing = self._workers.get(worker_id)
        worker = Worker(
            worker_id=worker_id,
            hostname=hostname,
            status=WorkerStatus.ONLINE,
            last_heartbeat=now,
            capabilities=[WorkerCapability(node_name=name) for name in capabilities],
            active_tasks=list(existing.active_tasks) if existing else [],
            maximum_parallel_tasks=maximum_parallel_tasks,
            metadata=metadata or {},
            registered_at=existing.registered_at if existing else now,
        )
        self._workers[worker_id] = worker
        return worker

    def get(self, worker_id: str) -> Worker:
        """Fetch a worker. Raises WorkerNotFoundError if unknown."""
        worker = self._workers.get(worker_id)
        if worker is None:
            raise WorkerNotFoundError(f"No worker found for '{worker_id}'.")
        return worker

    def list_all(self) -> list[Worker]:
        """Every registered worker, in registration order."""
        return list(self._workers.values())

    def list_by_status(self, status: WorkerStatus) -> list[Worker]:
        """Every worker currently in the given status."""
        return [worker for worker in self._workers.values() if worker.status == status]

    def list_supporting(self, node_name: str) -> list[Worker]:
        """Every worker that advertises ``node_name`` as a capability."""
        return [worker for worker in self._workers.values() if worker.supports(node_name)]

    def put(self, worker: Worker) -> Worker:
        """Store (overwrite) a worker snapshot, keyed by its own worker_id."""
        self._workers[worker.worker_id] = worker
        return worker

    def set_status(self, worker_id: str, status: WorkerStatus) -> Worker:
        """Transition a worker to a new status."""
        return self.put(self.get(worker_id).model_copy(update={"status": status}))

    def record_heartbeat(self, worker_id: str, now: datetime | None = None) -> Worker:
        """Record a heartbeat: refresh last_heartbeat, and revive an OFFLINE/FAILED worker to ONLINE."""
        worker = self.get(worker_id)
        update: dict[str, Any] = {"last_heartbeat": now or utc_now()}
        if worker.status in {WorkerStatus.OFFLINE, WorkerStatus.FAILED}:
            update["status"] = WorkerStatus.ONLINE
        return self.put(worker.model_copy(update=update))

    def add_active_task(self, worker_id: str, assignment_id: str) -> Worker:
        """Credit one more active task to a worker, promoting it to BUSY at capacity."""
        worker = self.get(worker_id)
        active_tasks = [*worker.active_tasks, assignment_id]
        status = WorkerStatus.BUSY if len(active_tasks) >= worker.maximum_parallel_tasks else worker.status
        return self.put(worker.model_copy(update={"active_tasks": active_tasks, "status": status}))

    def remove_active_task(self, worker_id: str, assignment_id: str) -> Worker:
        """Release one active task from a worker, demoting BUSY back to ONLINE once under capacity."""
        worker = self.get(worker_id)
        active_tasks = [task_id for task_id in worker.active_tasks if task_id != assignment_id]
        status = worker.status
        if status == WorkerStatus.BUSY and len(active_tasks) < worker.maximum_parallel_tasks:
            status = WorkerStatus.ONLINE
        return self.put(worker.model_copy(update={"active_tasks": active_tasks, "status": status}))

    def remove(self, worker_id: str) -> None:
        """Deregister a worker entirely. A no-op if already absent."""
        self._workers.pop(worker_id, None)
