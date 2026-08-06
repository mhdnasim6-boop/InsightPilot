"""Tests for backend.distributed.heartbeat: HeartbeatManager and WorkerMonitor."""

from datetime import timedelta

from backend.distributed.heartbeat.heartbeat_manager import HeartbeatManager
from backend.distributed.heartbeat.worker_monitor import WorkerMonitor
from backend.distributed.models.worker_status import WorkerStatus
from backend.distributed.registry.worker_registry import WorkerRegistry
from backend.distributed.scheduler.lease_manager import LeaseManager
from backend.utils.time import utc_now


def test_heartbeat_manager_records_and_renews_leases() -> None:
    registry = WorkerRegistry()
    registry.register("w1", "h1", ["browser_agent"])
    lease_manager = LeaseManager(ttl_seconds=10)
    lease = lease_manager.grant("a1", "w1", now=utc_now())
    manager = HeartbeatManager(registry, lease_manager)

    worker, heartbeat = manager.record("w1", active_task_count=1)

    assert worker.last_heartbeat == heartbeat.received_at
    renewed_lease = lease_manager.get(lease.lease_id)
    assert renewed_lease.renewed_count == 1
    assert heartbeat.active_task_count == 1


def test_heartbeat_manager_history_is_bounded() -> None:
    registry = WorkerRegistry()
    registry.register("w1", "h1", ["browser_agent"])
    manager = HeartbeatManager(registry, LeaseManager())

    for _ in range(25):
        manager.record("w1")

    assert len(manager.history_for("w1")) == 20


def test_heartbeat_manager_latency_seconds() -> None:
    registry = WorkerRegistry()
    worker = registry.register("w1", "h1", ["browser_agent"])
    manager = HeartbeatManager(registry, LeaseManager())

    latency = manager.latency_seconds(worker, now=worker.last_heartbeat + timedelta(seconds=5))
    assert latency == 5.0


def test_heartbeat_manager_latency_is_none_without_a_heartbeat() -> None:
    from backend.distributed.models.worker import Worker

    worker = Worker(worker_id="w1", hostname="h1")
    manager = HeartbeatManager(WorkerRegistry(), LeaseManager())
    assert manager.latency_seconds(worker) is None


def test_worker_monitor_marks_stale_workers_offline() -> None:
    registry = WorkerRegistry()
    worker = registry.register("w1", "h1", ["browser_agent"])
    monitor = WorkerMonitor(registry, timeout_seconds=30)

    newly_offline = monitor.sweep(now=worker.last_heartbeat + timedelta(seconds=31))

    assert [w.worker_id for w in newly_offline] == ["w1"]
    assert registry.get("w1").status == WorkerStatus.OFFLINE


def test_worker_monitor_leaves_fresh_workers_alone() -> None:
    registry = WorkerRegistry()
    worker = registry.register("w1", "h1", ["browser_agent"])
    monitor = WorkerMonitor(registry, timeout_seconds=30)

    newly_offline = monitor.sweep(now=worker.last_heartbeat + timedelta(seconds=5))

    assert newly_offline == []
    assert registry.get("w1").status == WorkerStatus.ONLINE


def test_worker_monitor_never_touches_already_offline_workers() -> None:
    registry = WorkerRegistry()
    registry.register("w1", "h1", ["browser_agent"])
    registry.set_status("w1", WorkerStatus.OFFLINE)
    monitor = WorkerMonitor(registry, timeout_seconds=30)

    assert monitor.sweep() == []
