"""WorkerRecovery: reclaims every outstanding task credited to one lost worker.

Called once per worker that ``WorkerMonitor.sweep()`` just marked
OFFLINE — delegates each individual assignment to ``TaskRecovery``, never
duplicating its own "check real execution state first" logic.
"""

from backend.distributed.models.task_assignment import TaskAssignment
from backend.distributed.models.worker import Worker
from backend.distributed.queue.task_queue import TaskQueue
from backend.distributed.recovery.task_recovery import TaskRecovery


class WorkerRecovery:
    """Reclaims every TaskAssignment still credited to a worker that just went offline."""

    def __init__(self, task_queue: TaskQueue, task_recovery: TaskRecovery) -> None:
        self._task_queue = task_queue
        self._task_recovery = task_recovery

    def recover(self, worker: Worker) -> list[TaskAssignment]:
        """Reclaim every outstanding assignment for ``worker``. Returns the reclaimed assignments."""
        return [self._task_recovery.reclaim(assignment) for assignment in self._task_queue.for_worker(worker.worker_id)]
