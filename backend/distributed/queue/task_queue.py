"""TaskQueue: every currently pending/active TaskAssignment, keyed by assignment_id."""

from backend.distributed.models.task_assignment import TaskAssignment
from backend.distributed.queue.distributed_queue import DistributedQueue


class TaskQueue(DistributedQueue[TaskAssignment]):
    """Active TaskAssignments — dispatched but not yet completed/failed/requeued."""

    def enqueue_assignment(self, assignment: TaskAssignment) -> TaskAssignment:
        """Add (or replace) one assignment, keyed by its own assignment_id."""
        return self.enqueue(assignment.assignment_id, assignment)

    def for_worker(self, worker_id: str) -> list[TaskAssignment]:
        """Every currently queued assignment credited to ``worker_id``."""
        return [assignment for assignment in self.list_all() if assignment.worker_id == worker_id]
