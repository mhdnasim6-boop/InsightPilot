"""DispatchScheduler: decides which worker a step is credited to, and tracks
that credit through to completion/failure.

This is the one piece of "scheduling" this phase adds, and it is
deliberately narrow: it never runs a step itself (``ExecutionService``/
``DAGScheduler``/``NodeDispatcher`` already do that, unchanged) — it only
answers "which registered worker, if any, is this step assigned to" and
records a ``TaskAssignment``/``Lease`` for it. Returns ``None`` from
``dispatch()`` whenever no eligible worker exists, which is the normal
case for every deployment that hasn't registered any workers yet — the
real step still executes exactly as it always has, in-process.
"""

from typing import Any, Protocol, runtime_checkable

from backend.distributed.models.task_assignment import (
    TaskAssignment,
    TaskAssignmentStatus,
)
from backend.distributed.queue.task_queue import TaskQueue
from backend.distributed.registry.worker_registry import WorkerRegistry
from backend.distributed.scheduler.lease_manager import LeaseManager
from backend.distributed.scheduler.worker_selector import WorkerSelector
from backend.execution.dispatcher.node_dispatcher import AgentService
from backend.planning.models.step import ExecutionStep
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class DispatchScheduler:
    """Assigns steps to workers and tracks each assignment's lifecycle."""

    def __init__(
        self,
        worker_selector: WorkerSelector,
        worker_registry: WorkerRegistry,
        lease_manager: LeaseManager,
        task_queue: TaskQueue,
    ) -> None:
        self._worker_selector = worker_selector
        self._worker_registry = worker_registry
        self._lease_manager = lease_manager
        self._task_queue = task_queue

    def dispatch(self, node_name: str, step_id: str, plan_id: str | None = None) -> TaskAssignment | None:
        """Select a worker for ``node_name`` and record the assignment. None if none qualify."""
        worker = self._worker_selector.select_for(node_name)
        if worker is None:
            return None

        assignment_id = generate_id()
        lease = self._lease_manager.grant(assignment_id, worker.worker_id)
        assignment = TaskAssignment(
            assignment_id=assignment_id,
            step_id=step_id,
            plan_id=plan_id,
            node_name=node_name,
            worker_id=worker.worker_id,
            lease_id=lease.lease_id,
            status=TaskAssignmentStatus.RUNNING,
            assigned_at=utc_now(),
        )
        self._task_queue.enqueue_assignment(assignment)
        self._worker_registry.add_active_task(worker.worker_id, assignment_id)
        return assignment

    def complete(self, assignment_id: str) -> TaskAssignment | None:
        """Mark an assignment COMPLETED, release its lease and worker capacity."""
        return self._finish(assignment_id, TaskAssignmentStatus.COMPLETED, error=None)

    def fail(self, assignment_id: str, error: str) -> TaskAssignment | None:
        """Mark an assignment FAILED, release its lease and worker capacity."""
        return self._finish(assignment_id, TaskAssignmentStatus.FAILED, error=error)

    def _finish(
        self, assignment_id: str, status: TaskAssignmentStatus, error: str | None
    ) -> TaskAssignment | None:
        assignment = self._task_queue.remove(assignment_id)
        if assignment is None:
            return None
        finished = assignment.model_copy(update={"status": status, "completed_at": utc_now(), "error": error})
        self._lease_manager.release(assignment.lease_id)
        self._worker_registry.remove_active_task(assignment.worker_id, assignment_id)
        return finished


@runtime_checkable
class DispatchTarget(Protocol):
    """The narrow slice of ``DistributedExecutionService`` ``DispatchingAgentService``
    needs — a ``Protocol`` (not a direct import) so this module never depends on
    ``backend.distributed.services``, which itself depends on this one."""

    def assign(self, node_name: str, step_id: str, plan_id: str | None = None) -> TaskAssignment | None: ...
    def complete(self, assignment_id: str) -> TaskAssignment | None: ...
    def fail(self, assignment_id: str, error: str) -> TaskAssignment | None: ...


class DispatchingAgentService:
    """Wraps a real ``AgentService``, crediting an eligible registered worker (if any)
    with the step before delegating — mirrors the exact
    ``backend.realtime.publishers.execution_publisher.RealtimePublishingAgentService``
    shape (wrap, act around the call, delegate, never reimplement). Wired into
    ``get_node_dispatcher()`` (``backend.dependencies.execution``), alongside — not
    instead of — that same realtime decorator.

    ``plan_id`` is always ``None`` here: ``NodeDispatcher.dispatch()`` only ever
    receives an ``ExecutionStep``/``session_id``, and ``ExecutionStep`` itself carries
    no ``plan_id`` field — a real, honest structural limit of this integration seam,
    not an oversight. ``TaskRecovery``'s own "check real execution state before
    requeuing" cross-check (which needs a ``plan_id``) simply doesn't apply to
    assignments created this way; it fully applies to assignments created with an
    explicit ``plan_id`` (e.g. directly through ``DistributedExecutionService.assign()``).
    """

    def __init__(self, node_name: str, inner: AgentService, distributed_execution_service: DispatchTarget) -> None:
        self._node_name = node_name
        self._inner = inner
        self._distributed_execution_service = distributed_execution_service

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> Any:
        assignment = self._distributed_execution_service.assign(self._node_name, step.step_id)
        try:
            result = await self._inner.execute_step(step, session_id)
        except Exception as exc:
            if assignment is not None:
                self._distributed_execution_service.fail(assignment.assignment_id, str(exc))
            raise
        if assignment is not None:
            self._distributed_execution_service.complete(assignment.assignment_id)
        return result
