"""TaskRecovery: reclaims one TaskAssignment whose lease/worker was lost.

"Do not lose execution state" is made concrete by reusing the real
``ExecutionCheckpointStore`` (Phase 27) directly, never a second,
parallel record of "did this step actually finish": before requeuing an
assignment, this checks whether the real ``ExecutionState`` already
recorded that step as COMPLETED/FAILED — since the step's own real
in-process execution (``NodeDispatcher``/``DAGScheduler``) is the single
source of truth for what actually happened, a stale assignment must
never be blindly re-run/duplicated just because its bookkeeping lease
expired.
"""

from backend.distributed.models.task_assignment import (
    TaskAssignment,
    TaskAssignmentStatus,
)
from backend.distributed.queue.retry_queue import RetryQueue
from backend.distributed.queue.task_queue import TaskQueue
from backend.distributed.registry.worker_registry import WorkerRegistry
from backend.distributed.scheduler.lease_manager import LeaseManager
from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore
from backend.execution.state.node_status import NodeStatus
from backend.utils.time import utc_now

_TERMINAL_NODE_STATUSES = frozenset({NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.CANCELLED})


class TaskRecovery:
    """Reclaims one lost TaskAssignment, checking real execution state first."""

    def __init__(
        self,
        task_queue: TaskQueue,
        retry_queue: RetryQueue,
        lease_manager: LeaseManager,
        worker_registry: WorkerRegistry,
        checkpoint_store: ExecutionCheckpointStore,
    ) -> None:
        self._task_queue = task_queue
        self._retry_queue = retry_queue
        self._lease_manager = lease_manager
        self._worker_registry = worker_registry
        self._checkpoint_store = checkpoint_store

    def reclaim(self, assignment: TaskAssignment) -> TaskAssignment:
        """Reclaim one assignment: drop the lease/worker credit, then either mark it
        COMPLETED (if the real execution state already shows it finished) or REQUEUED
        (into the retry queue, for a future dispatch) — never both, never silently lost.
        """
        self._lease_manager.release(assignment.lease_id)
        self._worker_registry.remove_active_task(assignment.worker_id, assignment.assignment_id)
        self._task_queue.remove(assignment.assignment_id)

        if self._already_finished(assignment):
            return assignment.model_copy(update={"status": TaskAssignmentStatus.COMPLETED, "completed_at": utc_now()})

        reclaimed = assignment.model_copy(
            update={"status": TaskAssignmentStatus.REQUEUED, "retry_count": assignment.retry_count + 1}
        )
        self._retry_queue.enqueue_assignment(reclaimed)
        return reclaimed

    def _already_finished(self, assignment: TaskAssignment) -> bool:
        if assignment.plan_id is None:
            return False
        checkpoints = self._checkpoint_store.list_for_plan(assignment.plan_id)
        if not checkpoints:
            return False
        step_state = checkpoints[0].state.steps.get(assignment.step_id)
        return step_state is not None and step_state.status in _TERMINAL_NODE_STATUSES
