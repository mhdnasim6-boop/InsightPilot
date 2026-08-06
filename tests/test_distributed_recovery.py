"""Tests for backend.distributed.recovery: TaskRecovery and WorkerRecovery."""

from backend.distributed.models.task_assignment import (
    TaskAssignment,
    TaskAssignmentStatus,
)
from backend.distributed.queue.retry_queue import RetryQueue
from backend.distributed.queue.task_queue import TaskQueue
from backend.distributed.recovery.task_recovery import TaskRecovery
from backend.distributed.recovery.worker_recovery import WorkerRecovery
from backend.distributed.registry.worker_registry import WorkerRegistry
from backend.distributed.scheduler.lease_manager import LeaseManager
from backend.execution.checkpoint.execution_checkpoint import (
    ExecutionCheckpoint,
    ExecutionCheckpointStore,
)
from backend.execution.state.execution_state import ExecutionState, StepExecutionState
from backend.execution.state.node_status import NodeStatus
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.utils.time import utc_now


def _assignment(plan_id: str | None, worker_id: str = "w1") -> TaskAssignment:
    return TaskAssignment(
        assignment_id="a1", step_id="s1", plan_id=plan_id, node_name="browser_agent",
        worker_id=worker_id, lease_id="l1", status=TaskAssignmentStatus.RUNNING, assigned_at=utc_now(),
    )


def _recovery() -> tuple[TaskRecovery, TaskQueue, RetryQueue, WorkerRegistry, LeaseManager, ExecutionCheckpointStore]:
    task_queue = TaskQueue()
    retry_queue = RetryQueue()
    lease_manager = LeaseManager()
    worker_registry = WorkerRegistry()
    checkpoint_store = ExecutionCheckpointStore()
    recovery = TaskRecovery(task_queue, retry_queue, lease_manager, worker_registry, checkpoint_store)
    return recovery, task_queue, retry_queue, worker_registry, lease_manager, checkpoint_store


def test_reclaim_requeues_when_no_plan_id() -> None:
    recovery, task_queue, retry_queue, worker_registry, lease_manager, _ = _recovery()
    worker_registry.register("w1", "h1", ["browser_agent"])
    worker_registry.add_active_task("w1", "a1")
    lease_manager.grant("a1", "w1")
    task_queue.enqueue_assignment(_assignment(plan_id=None))

    reclaimed = recovery.reclaim(_assignment(plan_id=None))

    assert reclaimed.status == TaskAssignmentStatus.REQUEUED
    assert reclaimed.retry_count == 1
    assert retry_queue.get("a1") == reclaimed
    assert worker_registry.get("w1").active_tasks == []


def test_reclaim_recognizes_already_completed_step_via_checkpoint() -> None:
    recovery, task_queue, retry_queue, worker_registry, lease_manager, checkpoint_store = _recovery()
    worker_registry.register("w1", "h1", ["browser_agent"])
    worker_registry.add_active_task("w1", "a1")
    lease_manager.grant("a1", "w1")
    assignment = _assignment(plan_id="p1")
    task_queue.enqueue_assignment(assignment)

    checkpoint_store.put(
        ExecutionCheckpoint(
            execution_id="e1", plan_id="p1", plan=ExecutionPlan(plan_id="p1", created_at=utc_now(), updated_at=utc_now()),
            state=ExecutionState(
                execution_id="e1", plan_id="p1", status=PlanStatus.RUNNING,
                steps={"s1": StepExecutionState(step_id="s1", node_name="browser_agent", status=NodeStatus.COMPLETED)},
                created_at=utc_now(), updated_at=utc_now(),
            ),
            checkpointed_at=utc_now(),
        )
    )

    reclaimed = recovery.reclaim(assignment)

    assert reclaimed.status == TaskAssignmentStatus.COMPLETED
    assert retry_queue.get("a1") is None


def test_reclaim_requeues_when_checkpoint_shows_step_still_pending() -> None:
    recovery, task_queue, retry_queue, worker_registry, lease_manager, checkpoint_store = _recovery()
    worker_registry.register("w1", "h1", ["browser_agent"])
    worker_registry.add_active_task("w1", "a1")
    lease_manager.grant("a1", "w1")
    assignment = _assignment(plan_id="p1")
    task_queue.enqueue_assignment(assignment)

    checkpoint_store.put(
        ExecutionCheckpoint(
            execution_id="e1", plan_id="p1", plan=ExecutionPlan(plan_id="p1", created_at=utc_now(), updated_at=utc_now()),
            state=ExecutionState(
                execution_id="e1", plan_id="p1", status=PlanStatus.RUNNING,
                steps={"s1": StepExecutionState(step_id="s1", node_name="browser_agent", status=NodeStatus.RUNNING)},
                created_at=utc_now(), updated_at=utc_now(),
            ),
            checkpointed_at=utc_now(),
        )
    )

    reclaimed = recovery.reclaim(assignment)

    assert reclaimed.status == TaskAssignmentStatus.REQUEUED
    assert retry_queue.get("a1") == reclaimed


def test_worker_recovery_reclaims_every_task_for_a_lost_worker() -> None:
    task_queue = TaskQueue()
    retry_queue = RetryQueue()
    lease_manager = LeaseManager()
    worker_registry = WorkerRegistry()
    checkpoint_store = ExecutionCheckpointStore()
    worker_registry.register("w1", "h1", ["browser_agent"], maximum_parallel_tasks=2)
    worker_registry.add_active_task("w1", "a1")
    worker_registry.add_active_task("w1", "a2")
    lease_manager.grant("a1", "w1")
    lease_manager.grant("a2", "w1")
    task_queue.enqueue_assignment(_assignment(plan_id=None, worker_id="w1"))
    task_queue.enqueue_assignment(
        _assignment(plan_id=None, worker_id="w1").model_copy(update={"assignment_id": "a2"})
    )
    task_recovery = TaskRecovery(task_queue, retry_queue, lease_manager, worker_registry, checkpoint_store)
    worker_recovery = WorkerRecovery(task_queue, task_recovery)

    reclaimed = worker_recovery.recover(worker_registry.get("w1"))

    assert {a.assignment_id for a in reclaimed} == {"a1", "a2"}
    assert len(retry_queue) == 2
    assert worker_registry.get("w1").active_tasks == []
