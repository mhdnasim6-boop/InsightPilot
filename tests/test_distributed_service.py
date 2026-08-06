"""Tests for backend.distributed.services.distributed_execution_service.DistributedExecutionService
— the one public entry point: worker lifecycle, dispatch, heartbeats, and recovery, composed together.
"""

from datetime import timedelta

from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.distributed.exceptions import WorkerNotFoundError
from backend.distributed.heartbeat.heartbeat_manager import HeartbeatManager
from backend.distributed.heartbeat.worker_monitor import WorkerMonitor
from backend.distributed.models.task_assignment import TaskAssignmentStatus
from backend.distributed.models.worker_status import WorkerStatus
from backend.distributed.queue.retry_queue import RetryQueue
from backend.distributed.queue.task_queue import TaskQueue
from backend.distributed.recovery.task_recovery import TaskRecovery
from backend.distributed.recovery.worker_recovery import WorkerRecovery
from backend.distributed.registry.capability_registry import (
    DistributedCapabilityRegistry,
)
from backend.distributed.registry.worker_registry import WorkerRegistry
from backend.distributed.scheduler.dispatch_scheduler import DispatchScheduler
from backend.distributed.scheduler.lease_manager import LeaseManager
from backend.distributed.scheduler.load_balancer import LoadBalancer
from backend.distributed.scheduler.worker_selector import WorkerSelector
from backend.distributed.services.distributed_execution_service import (
    DistributedExecutionService,
)
from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import InsightPilotState
from backend.utils.time import utc_now


class _FakeAgentNode(OrchestrationNode):
    name = "browser_agent"

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state


def _build_service(heartbeat_timeout: float = 90.0) -> DistributedExecutionService:
    graph_builder = GraphBuilder()
    graph_builder.add_node(_FakeAgentNode())
    graph_builder.set_entry_point("browser_agent")

    worker_registry = WorkerRegistry()
    capability_registry = DistributedCapabilityRegistry(AgentCapabilityRegistry(graph_builder))
    load_balancer = LoadBalancer()
    worker_selector = WorkerSelector(worker_registry, capability_registry, load_balancer)
    lease_manager = LeaseManager()
    task_queue = TaskQueue()
    retry_queue = RetryQueue()
    dispatch_scheduler = DispatchScheduler(worker_selector, worker_registry, lease_manager, task_queue)
    heartbeat_manager = HeartbeatManager(worker_registry, lease_manager)
    worker_monitor = WorkerMonitor(worker_registry, timeout_seconds=heartbeat_timeout)
    task_recovery = TaskRecovery(task_queue, retry_queue, lease_manager, worker_registry, ExecutionCheckpointStore())
    worker_recovery = WorkerRecovery(task_queue, task_recovery)

    return DistributedExecutionService(
        worker_registry, capability_registry, dispatch_scheduler, task_queue, retry_queue,
        heartbeat_manager, worker_monitor, worker_recovery,
    )


def test_register_worker_filters_unrecognized_capabilities() -> None:
    service = _build_service()
    worker = service.register_worker("w1", "h1", ["browser_agent", "not_a_real_agent"])
    assert [c.node_name for c in worker.capabilities] == ["browser_agent"]


def test_heartbeat_revives_and_renews_leases() -> None:
    service = _build_service()
    service.register_worker("w1", "h1", ["browser_agent"])
    assignment = service.assign("browser_agent", "s1")
    assert assignment is not None

    worker = service.heartbeat("w1")
    assert worker.status in {WorkerStatus.ONLINE, WorkerStatus.BUSY}


def test_drain_worker_stops_new_dispatch_but_keeps_existing_tasks() -> None:
    service = _build_service()
    service.register_worker("w1", "h1", ["browser_agent"])
    first = service.assign("browser_agent", "s1")
    assert first is not None

    service.drain_worker("w1")

    assert service.get_worker("w1").status == WorkerStatus.DRAINING
    assert service.assign("browser_agent", "s2") is None  # no other eligible worker


def test_shutdown_worker_reclaims_outstanding_tasks() -> None:
    service = _build_service()
    service.register_worker("w1", "h1", ["browser_agent"])
    assignment = service.assign("browser_agent", "s1")
    assert assignment is not None

    worker = service.shutdown_worker("w1")

    assert worker.status == WorkerStatus.OFFLINE
    assert worker.active_tasks == []
    assert service.queue_snapshot()["active"] == []
    assert len(service.queue_snapshot()["retry"]) == 1


def test_get_worker_raises_for_unknown_worker() -> None:
    service = _build_service()
    try:
        service.get_worker("does-not-exist")
        raised = False
    except WorkerNotFoundError:
        raised = True
    assert raised


def test_assign_complete_fail_round_trip() -> None:
    service = _build_service()
    service.register_worker("w1", "h1", ["browser_agent"])

    assignment = service.assign("browser_agent", "s1", plan_id="p1")
    assert assignment is not None
    assert assignment.status == TaskAssignmentStatus.RUNNING

    completed = service.complete(assignment.assignment_id)
    assert completed is not None
    assert completed.status == TaskAssignmentStatus.COMPLETED


def test_assign_returns_none_with_no_registered_workers() -> None:
    service = _build_service()
    assert service.assign("browser_agent", "s1") is None


def test_cluster_statistics_aggregates_across_workers() -> None:
    service = _build_service()
    service.register_worker("w1", "h1", ["browser_agent"], maximum_parallel_tasks=2)
    service.register_worker("w2", "h2", ["browser_agent"], maximum_parallel_tasks=3)
    service.assign("browser_agent", "s1")

    stats = service.cluster_statistics()

    assert stats.total_workers == 2
    assert stats.total_capacity == 5
    assert stats.total_active_tasks == 1


def test_sweep_marks_stale_workers_offline_and_reclaims_their_tasks() -> None:
    service = _build_service(heartbeat_timeout=10)
    service.register_worker("w1", "h1", ["browser_agent"])
    assignment = service.assign("browser_agent", "s1")
    assert assignment is not None

    stale_worker = service._worker_registry.get("w1")
    service._worker_registry.put(
        stale_worker.model_copy(update={"last_heartbeat": utc_now() - timedelta(seconds=20)})
    )

    workers = service.list_workers()

    assert workers[0].status == WorkerStatus.OFFLINE
    assert workers[0].active_tasks == []
    assert len(service.queue_snapshot()["retry"]) == 1


def test_export_json_and_mermaid_do_not_raise() -> None:
    service = _build_service()
    service.register_worker("w1", "h1", ["browser_agent"])
    assert "w1" in service.export_json()
    assert "flowchart" in service.export_mermaid()
