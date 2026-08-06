"""RetryQueue: TaskAssignments reclaimed by recovery, awaiting re-dispatch.

A separate queue from ``TaskQueue`` (rather than a status flag on the
same entry) so "what's currently running" and "what needs a human/scheduler
to look at" are two distinctly inspectable collections — mirrors keeping
``ApprovalStore``'s pending list conceptually separate from its decided
history.
"""

from backend.distributed.models.task_assignment import TaskAssignment
from backend.distributed.queue.distributed_queue import DistributedQueue


class RetryQueue(DistributedQueue[TaskAssignment]):
    """TaskAssignments whose worker/lease was lost, awaiting reassignment."""

    def enqueue_assignment(self, assignment: TaskAssignment) -> TaskAssignment:
        """Add (or replace) one reclaimed assignment, keyed by its own assignment_id."""
        return self.enqueue(assignment.assignment_id, assignment)
