"""Tests for backend.distributed.models: Worker, Lease, TaskAssignment behavior."""

from datetime import timedelta

from backend.distributed.models.lease import Lease
from backend.distributed.models.task_assignment import (
    TaskAssignment,
    TaskAssignmentStatus,
)
from backend.distributed.models.worker import Worker
from backend.distributed.models.worker_capability import WorkerCapability
from backend.distributed.models.worker_status import WorkerStatus
from backend.utils.time import utc_now


def _worker(**overrides: object) -> Worker:
    defaults: dict[str, object] = {
        "worker_id": "w1", "hostname": "host-1",
        "capabilities": [WorkerCapability(node_name="browser_agent")],
        "maximum_parallel_tasks": 2,
    }
    defaults.update(overrides)
    return Worker(**defaults)  # type: ignore[arg-type]


def test_worker_supports_checks_capabilities() -> None:
    worker = _worker()
    assert worker.supports("browser_agent")
    assert not worker.supports("sql_agent")


def test_worker_has_capacity_respects_maximum() -> None:
    worker = _worker(active_tasks=["a1"], maximum_parallel_tasks=2)
    assert worker.has_capacity()
    full = _worker(active_tasks=["a1", "a2"], maximum_parallel_tasks=2)
    assert not full.has_capacity()


def test_worker_load_ratio() -> None:
    worker = _worker(active_tasks=["a1"], maximum_parallel_tasks=4)
    assert worker.load_ratio() == 0.25


def test_worker_is_frozen() -> None:
    worker = _worker()
    try:
        worker.status = WorkerStatus.OFFLINE  # type: ignore[misc]
        raised = False
    except Exception:  # noqa: BLE001 - just proving immutability, not testing pydantic's own error type
        raised = True
    assert raised


def test_lease_is_expired() -> None:
    now = utc_now()
    lease = Lease(lease_id="l1", assignment_id="a1", worker_id="w1", granted_at=now, expires_at=now + timedelta(seconds=10))
    assert not lease.is_expired(now)
    assert lease.is_expired(now + timedelta(seconds=11))


def test_task_assignment_defaults_to_assigned_status() -> None:
    assignment = TaskAssignment(
        assignment_id="a1", step_id="s1", node_name="browser_agent", worker_id="w1", lease_id="l1",
        assigned_at=utc_now(),
    )
    assert assignment.status == TaskAssignmentStatus.ASSIGNED
    assert assignment.retry_count == 0
