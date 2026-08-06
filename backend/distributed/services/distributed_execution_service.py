"""DistributedExecutionService: the ONLY public entry point for the distributed layer.

Composes every collaborator in ``backend/distributed/`` — registry,
scheduler, queues, heartbeat, recovery — into one facade, mirroring
``WorkflowService``/``RealtimeService``'s own "one object, everything
goes through it" shape.

**Why "workers" don't actually run anything remotely.** InsightPilot is
one FastAPI process with no message broker, no RPC transport, and no
requirement to add one in this phase. A registered ``Worker`` is a real,
independently-tracked capacity/lease record — a real external process
(or a pool of them) can call ``register_worker()``/``heartbeat()``/
``drain_worker()``/``shutdown_worker()`` over the REST API exactly as
this phase's own contract describes — but the step it's credited with
still executes in-process, through the same real agent service Phase
1-37 already built (``NodeDispatcher``/``DAGScheduler``/``ExecutionService``
are never modified, never duplicated). ``assign()`` is called from a
thin decorator wired into ``get_node_dispatcher()`` (see
``backend.dependencies.execution``), *around* the real step call: it
decides which registered worker is credited, but the `await` on the
actual agent call happens exactly where it always has. With zero
workers registered — every existing test, and any deployment that
hasn't opted in — ``assign()`` always returns ``None`` and every
existing execution path behaves identically to before this phase
existed. This is the same honest, additive shape Phase 37 established
for realtime events: real primitives, wired into a real seam, without
inventing infrastructure this codebase was never asked to add.

Every read/heartbeat method sweeps for stale workers first
(``WorkerMonitor.sweep()``) and recovers any that just went offline
(``WorkerRecovery.recover()``) — a lazy, on-access check, since this
codebase has no precedent for a recurring background timer.
"""

from typing import Any

from backend.distributed.exporters.json_exporter import export_cluster_json
from backend.distributed.exporters.mermaid_exporter import export_cluster_mermaid
from backend.distributed.heartbeat.heartbeat_manager import HeartbeatManager
from backend.distributed.heartbeat.worker_monitor import WorkerMonitor
from backend.distributed.models.cluster_statistics import ClusterStatistics
from backend.distributed.models.task_assignment import TaskAssignment
from backend.distributed.models.worker import Worker
from backend.distributed.models.worker_status import WorkerStatus
from backend.distributed.queue.retry_queue import RetryQueue
from backend.distributed.queue.task_queue import TaskQueue
from backend.distributed.recovery.worker_recovery import WorkerRecovery
from backend.distributed.registry.capability_registry import (
    DistributedCapabilityRegistry,
)
from backend.distributed.registry.worker_registry import WorkerRegistry
from backend.distributed.scheduler.dispatch_scheduler import DispatchScheduler
from backend.utils.time import utc_now


class DistributedExecutionService:
    """Runs the full lifecycle of worker registration, dispatch, heartbeats, and recovery."""

    def __init__(
        self,
        worker_registry: WorkerRegistry,
        capability_registry: DistributedCapabilityRegistry,
        dispatch_scheduler: DispatchScheduler,
        task_queue: TaskQueue,
        retry_queue: RetryQueue,
        heartbeat_manager: HeartbeatManager,
        worker_monitor: WorkerMonitor,
        worker_recovery: WorkerRecovery,
    ) -> None:
        self._worker_registry = worker_registry
        self._capability_registry = capability_registry
        self._dispatch_scheduler = dispatch_scheduler
        self._task_queue = task_queue
        self._retry_queue = retry_queue
        self._heartbeat_manager = heartbeat_manager
        self._worker_monitor = worker_monitor
        self._worker_recovery = worker_recovery

    # -- Worker lifecycle -----------------------------------------------------------

    def register_worker(
        self,
        worker_id: str,
        hostname: str,
        capabilities: list[str],
        maximum_parallel_tasks: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> Worker:
        """Register (or re-register) a worker. Unrecognized capabilities are silently
        dropped (see ``DistributedCapabilityRegistry``'s own docstring for why)."""
        recognized = self._capability_registry.recognized_capabilities(capabilities)
        return self._worker_registry.register(worker_id, hostname, recognized, maximum_parallel_tasks, metadata)

    def heartbeat(self, worker_id: str, active_task_count: int | None = None, metadata: dict[str, Any] | None = None) -> Worker:
        """Record a heartbeat: renews the worker's leases and revives it if it was OFFLINE."""
        self._sweep_and_recover()
        worker, _ = self._heartbeat_manager.record(worker_id, active_task_count, metadata)
        return worker

    def drain_worker(self, worker_id: str) -> Worker:
        """Stop routing new work to a worker; its existing tasks run to completion."""
        return self._worker_registry.set_status(worker_id, WorkerStatus.DRAINING)

    def shutdown_worker(self, worker_id: str) -> Worker:
        """Gracefully take a worker offline: reclaim its outstanding work first, then mark it OFFLINE."""
        worker = self._worker_registry.get(worker_id)
        self._worker_recovery.recover(worker)
        return self._worker_registry.set_status(worker_id, WorkerStatus.OFFLINE)

    def get_worker(self, worker_id: str) -> Worker:
        """Fetch one worker by id, after a staleness sweep."""
        self._sweep_and_recover()
        return self._worker_registry.get(worker_id)

    def list_workers(self) -> list[Worker]:
        """Every registered worker, after a staleness sweep."""
        self._sweep_and_recover()
        return self._worker_registry.list_all()

    # -- Dispatch (called from the NodeDispatcher-wrapping decorator) --------------

    def assign(self, node_name: str, step_id: str, plan_id: str | None = None) -> TaskAssignment | None:
        """Assign one step to an eligible worker, if any. None means "run locally, no worker credited"."""
        self._sweep_and_recover()
        return self._dispatch_scheduler.dispatch(node_name, step_id, plan_id)

    def complete(self, assignment_id: str) -> TaskAssignment | None:
        """Mark an assignment COMPLETED and release its worker/lease."""
        return self._dispatch_scheduler.complete(assignment_id)

    def fail(self, assignment_id: str, error: str) -> TaskAssignment | None:
        """Mark an assignment FAILED and release its worker/lease."""
        return self._dispatch_scheduler.fail(assignment_id, error)

    # -- Cluster / queue observability ---------------------------------------------

    def cluster_statistics(self) -> ClusterStatistics:
        """Aggregate counts across the whole fleet, after a staleness sweep."""
        self._sweep_and_recover()
        workers = self._worker_registry.list_all()
        by_status = {status: len([w for w in workers if w.status == status]) for status in WorkerStatus}
        return ClusterStatistics(
            total_workers=len(workers),
            online_workers=by_status[WorkerStatus.ONLINE],
            busy_workers=by_status[WorkerStatus.BUSY],
            offline_workers=by_status[WorkerStatus.OFFLINE],
            failed_workers=by_status[WorkerStatus.FAILED],
            draining_workers=by_status[WorkerStatus.DRAINING],
            total_active_tasks=sum(len(w.active_tasks) for w in workers),
            total_capacity=sum(w.maximum_parallel_tasks for w in workers),
            queue_depth=len(self._task_queue),
            retry_queue_depth=len(self._retry_queue),
            generated_at=utc_now(),
        )

    def queue_snapshot(self) -> dict[str, list[TaskAssignment]]:
        """Every currently active and retry-pending assignment."""
        return {"active": self._task_queue.list_all(), "retry": self._retry_queue.list_all()}

    def export_json(self) -> str:
        """Serialize the whole cluster (workers + active assignments + statistics) as JSON."""
        return export_cluster_json(self.list_workers(), self._task_queue.list_all(), self.cluster_statistics())

    def export_mermaid(self) -> str:
        """Render the worker fleet and its active assignments as a Mermaid flowchart."""
        return export_cluster_mermaid(self.list_workers(), self._task_queue.list_all())

    # -- Internal ---------------------------------------------------------------------

    def _sweep_and_recover(self) -> None:
        for worker in self._worker_monitor.sweep():
            self._worker_recovery.recover(worker)
