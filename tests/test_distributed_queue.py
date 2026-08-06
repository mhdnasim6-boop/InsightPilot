"""Tests for backend.distributed.queue: DistributedQueue, TaskQueue, RetryQueue."""

from backend.distributed.models.task_assignment import TaskAssignment
from backend.distributed.queue.distributed_queue import DistributedQueue
from backend.distributed.queue.retry_queue import RetryQueue
from backend.distributed.queue.task_queue import TaskQueue
from backend.utils.time import utc_now


def _assignment(assignment_id: str = "a1", worker_id: str = "w1") -> TaskAssignment:
    return TaskAssignment(
        assignment_id=assignment_id, step_id="s1", node_name="browser_agent", worker_id=worker_id,
        lease_id="l1", assigned_at=utc_now(),
    )


def test_distributed_queue_enqueue_get_remove() -> None:
    queue: DistributedQueue[str] = DistributedQueue()
    queue.enqueue("k1", "value")
    assert queue.get("k1") == "value"
    assert len(queue) == 1
    assert queue.remove("k1") == "value"
    assert queue.get("k1") is None
    assert len(queue) == 0


def test_distributed_queue_list_all_is_insertion_ordered() -> None:
    queue: DistributedQueue[str] = DistributedQueue()
    queue.enqueue("k1", "first")
    queue.enqueue("k2", "second")
    assert queue.list_all() == ["first", "second"]


def test_task_queue_enqueue_assignment_and_for_worker() -> None:
    queue = TaskQueue()
    queue.enqueue_assignment(_assignment("a1", "w1"))
    queue.enqueue_assignment(_assignment("a2", "w2"))
    assert [a.assignment_id for a in queue.for_worker("w1")] == ["a1"]


def test_retry_queue_enqueue_assignment() -> None:
    queue = RetryQueue()
    queue.enqueue_assignment(_assignment("a1"))
    assert len(queue) == 1
    assert queue.get("a1") is not None
