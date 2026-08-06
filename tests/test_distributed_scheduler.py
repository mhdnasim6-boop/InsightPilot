"""Tests for backend.distributed.scheduler: LoadBalancer, WorkerSelector,
LeaseManager, DispatchScheduler, and DispatchingAgentService.
"""

import asyncio
from datetime import timedelta

import pytest

from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.distributed.exceptions import LeaseNotFoundError
from backend.distributed.models.task_assignment import TaskAssignmentStatus
from backend.distributed.models.worker_status import WorkerStatus
from backend.distributed.queue.task_queue import TaskQueue
from backend.distributed.registry.capability_registry import (
    DistributedCapabilityRegistry,
)
from backend.distributed.registry.worker_registry import WorkerRegistry
from backend.distributed.scheduler.dispatch_scheduler import (
    DispatchingAgentService,
    DispatchScheduler,
)
from backend.distributed.scheduler.lease_manager import LeaseManager
from backend.distributed.scheduler.load_balancer import LoadBalancer
from backend.distributed.scheduler.worker_selector import WorkerSelector
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import InsightPilotState
from backend.planning.models.step import ExecutionStep
from backend.utils.time import utc_now


class _FakeAgentNode(OrchestrationNode):
    name = "browser_agent"

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state


def _capability_registry() -> DistributedCapabilityRegistry:
    graph_builder = GraphBuilder()
    graph_builder.add_node(_FakeAgentNode())
    graph_builder.set_entry_point("browser_agent")
    return DistributedCapabilityRegistry(AgentCapabilityRegistry(graph_builder))


def _selector(worker_registry: WorkerRegistry) -> WorkerSelector:
    return WorkerSelector(worker_registry, _capability_registry(), LoadBalancer())


def _step(step_id: str = "s1") -> ExecutionStep:
    return ExecutionStep(step_id=step_id, name="Search", node_name="browser_agent")


# -- LoadBalancer ---------------------------------------------------------------------


def test_load_balancer_returns_none_for_empty_candidates() -> None:
    assert LoadBalancer().select([]) is None


def test_load_balancer_picks_least_loaded() -> None:
    registry = WorkerRegistry()
    registry.register("busy", "h1", ["browser_agent"], maximum_parallel_tasks=2)
    registry.add_active_task("busy", "a1")
    registry.register("idle", "h2", ["browser_agent"], maximum_parallel_tasks=2)

    selected = LoadBalancer().select(registry.list_all())
    assert selected is not None
    assert selected.worker_id == "idle"


# -- WorkerSelector -------------------------------------------------------------------


def test_worker_selector_returns_none_for_unrecognized_capability() -> None:
    registry = WorkerRegistry()
    registry.register("w1", "h1", ["browser_agent"])
    assert _selector(registry).select_for("not_a_real_agent") is None


def test_worker_selector_returns_none_with_no_workers_registered() -> None:
    registry = WorkerRegistry()
    assert _selector(registry).select_for("browser_agent") is None


def test_worker_selector_excludes_offline_and_full_workers() -> None:
    registry = WorkerRegistry()
    registry.register("offline", "h1", ["browser_agent"])
    registry.set_status("offline", WorkerStatus.OFFLINE)
    registry.register("full", "h2", ["browser_agent"], maximum_parallel_tasks=1)
    registry.add_active_task("full", "a1")
    registry.register("eligible", "h3", ["browser_agent"])

    selected = _selector(registry).select_for("browser_agent")
    assert selected is not None
    assert selected.worker_id == "eligible"


# -- LeaseManager ---------------------------------------------------------------------


def test_lease_manager_grant_and_get() -> None:
    manager = LeaseManager(ttl_seconds=30)
    lease = manager.grant("a1", "w1")
    assert manager.get(lease.lease_id) == lease


def test_lease_manager_renew_extends_expiry() -> None:
    manager = LeaseManager(ttl_seconds=30)
    lease = manager.grant("a1", "w1")
    renewed = manager.renew(lease.lease_id, now=lease.granted_at + timedelta(seconds=10))
    assert renewed.expires_at > lease.expires_at
    assert renewed.renewed_count == 1


def test_lease_manager_release_removes_lease() -> None:
    manager = LeaseManager()
    lease = manager.grant("a1", "w1")
    manager.release(lease.lease_id)
    with pytest.raises(LeaseNotFoundError):
        manager.get(lease.lease_id)


def test_lease_manager_list_expired() -> None:
    manager = LeaseManager(ttl_seconds=10)
    lease = manager.grant("a1", "w1", now=utc_now())
    assert manager.list_expired(now=lease.granted_at + timedelta(seconds=5)) == []
    assert manager.list_expired(now=lease.granted_at + timedelta(seconds=11)) == [lease]


def test_lease_manager_renew_all_for_worker() -> None:
    manager = LeaseManager()
    manager.grant("a1", "w1")
    manager.grant("a2", "w1")
    manager.grant("a3", "w2")
    renewed = manager.renew_all_for_worker("w1")
    assert len(renewed) == 2


# -- DispatchScheduler ------------------------------------------------------------------


def _scheduler(registry: WorkerRegistry) -> tuple[DispatchScheduler, TaskQueue, LeaseManager]:
    lease_manager = LeaseManager()
    task_queue = TaskQueue()
    scheduler = DispatchScheduler(_selector(registry), registry, lease_manager, task_queue)
    return scheduler, task_queue, lease_manager


def test_dispatch_returns_none_with_no_eligible_worker() -> None:
    registry = WorkerRegistry()
    scheduler, _, _ = _scheduler(registry)
    assert scheduler.dispatch("browser_agent", "s1") is None


def test_dispatch_assigns_worker_and_credits_active_task() -> None:
    registry = WorkerRegistry()
    registry.register("w1", "h1", ["browser_agent"])
    scheduler, task_queue, lease_manager = _scheduler(registry)

    assignment = scheduler.dispatch("browser_agent", "s1", plan_id="p1")

    assert assignment is not None
    assert assignment.worker_id == "w1"
    assert assignment.status == TaskAssignmentStatus.RUNNING
    assert registry.get("w1").active_tasks == [assignment.assignment_id]
    assert task_queue.get(assignment.assignment_id) == assignment
    assert lease_manager.get(assignment.lease_id) is not None


def test_complete_releases_lease_and_worker_credit() -> None:
    registry = WorkerRegistry()
    registry.register("w1", "h1", ["browser_agent"], maximum_parallel_tasks=1)
    scheduler, task_queue, lease_manager = _scheduler(registry)
    assignment = scheduler.dispatch("browser_agent", "s1")
    assert assignment is not None

    completed = scheduler.complete(assignment.assignment_id)

    assert completed is not None
    assert completed.status == TaskAssignmentStatus.COMPLETED
    assert registry.get("w1").active_tasks == []
    assert registry.get("w1").status == WorkerStatus.ONLINE
    assert task_queue.get(assignment.assignment_id) is None
    with pytest.raises(LeaseNotFoundError):
        lease_manager.get(assignment.lease_id)


def test_fail_releases_lease_and_records_error() -> None:
    registry = WorkerRegistry()
    registry.register("w1", "h1", ["browser_agent"])
    scheduler, _, _ = _scheduler(registry)
    assignment = scheduler.dispatch("browser_agent", "s1")
    assert assignment is not None

    failed = scheduler.fail(assignment.assignment_id, "boom")

    assert failed is not None
    assert failed.status == TaskAssignmentStatus.FAILED
    assert failed.error == "boom"


def test_complete_unknown_assignment_returns_none() -> None:
    registry = WorkerRegistry()
    scheduler, _, _ = _scheduler(registry)
    assert scheduler.complete("does-not-exist") is None


# -- DispatchingAgentService ------------------------------------------------------------


class _FakeDispatchTarget:
    def __init__(self, assignment: object | None) -> None:
        self._assignment = assignment
        self.completed: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def assign(self, node_name: str, step_id: str, plan_id: str | None = None) -> object | None:
        return self._assignment

    def complete(self, assignment_id: str) -> None:
        self.completed.append(assignment_id)

    def fail(self, assignment_id: str, error: str) -> None:
        self.failed.append((assignment_id, error))


class _FakeAssignment:
    assignment_id = "a1"


class _FakeAgentService:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> str:
        if self.fail:
            raise RuntimeError("boom")
        return "ok"


def test_dispatching_agent_service_completes_assignment_on_success() -> None:
    target = _FakeDispatchTarget(_FakeAssignment())
    wrapped = DispatchingAgentService("browser_agent", _FakeAgentService(), target)  # type: ignore[arg-type]

    result = asyncio.run(wrapped.execute_step(_step(), "session-1"))

    assert result == "ok"
    assert target.completed == ["a1"]
    assert target.failed == []


def test_dispatching_agent_service_fails_assignment_and_reraises() -> None:
    target = _FakeDispatchTarget(_FakeAssignment())
    wrapped = DispatchingAgentService("browser_agent", _FakeAgentService(fail=True), target)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError):
        asyncio.run(wrapped.execute_step(_step(), None))

    assert target.failed == [("a1", "boom")]
    assert target.completed == []


def test_dispatching_agent_service_is_a_noop_with_no_available_worker() -> None:
    target = _FakeDispatchTarget(None)
    wrapped = DispatchingAgentService("browser_agent", _FakeAgentService(), target)  # type: ignore[arg-type]

    result = asyncio.run(wrapped.execute_step(_step(), None))

    assert result == "ok"
    assert target.completed == []
    assert target.failed == []
