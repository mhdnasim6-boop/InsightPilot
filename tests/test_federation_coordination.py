"""Tests for backend.federation.coordination: ClusterAllocator, WorkloadRouter,
and FederationCoordinator.
"""

import asyncio
from datetime import datetime

import pytest

from backend.federation.coordination.cluster_allocator import ClusterAllocator
from backend.federation.coordination.federation_coordinator import (
    FederationCoordinator,
)
from backend.federation.coordination.workload_router import WorkloadRouter
from backend.federation.models.cluster_capability import ClusterCapability
from backend.federation.models.remote_execution import RemoteExecutionStatus
from backend.federation.models.routing_decision import RoutingDecisionStatus
from backend.federation.registry.cluster_registry import ClusterRegistry
from backend.federation.registry.federation_directory import FederationDirectory
from backend.federation.scheduler.cluster_selector import ClusterSelector
from backend.federation.scheduler.failover_manager import FailoverManager
from backend.federation.scheduler.federation_scheduler import FederationScheduler
from backend.federation.scheduler.routing_engine import RoutingEngine


def _capabilities() -> ClusterCapability:
    return ClusterCapability(supported_agents=["browser_agent"], maximum_concurrent_executions=2)


def _registry_with_cluster() -> ClusterRegistry:
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities())
    return registry


# -- ClusterAllocator ---------------------------------------------------------------------


def test_allocate_credits_cluster_and_opens_remote_execution() -> None:
    registry = _registry_with_cluster()
    allocator = ClusterAllocator(registry)
    scheduler = FederationScheduler(ClusterSelector(FederationDirectory(registry), RoutingEngine()))
    decision = scheduler.schedule("wf1", ["browser_agent"], 1)

    remote_execution = allocator.allocate(decision)

    assert remote_execution.status == RemoteExecutionStatus.RUNNING
    assert registry.get("c1").active_remote_executions == [remote_execution.remote_execution_id]


def test_release_closes_execution_and_frees_capacity() -> None:
    registry = _registry_with_cluster()
    allocator = ClusterAllocator(registry)
    scheduler = FederationScheduler(ClusterSelector(FederationDirectory(registry), RoutingEngine()))
    decision = scheduler.schedule("wf1", ["browser_agent"], 1)
    remote_execution = allocator.allocate(decision)

    released = allocator.release(remote_execution.remote_execution_id, success=True)

    assert released.status == RemoteExecutionStatus.COMPLETED
    assert isinstance(released.completed_at, datetime)
    assert registry.get("c1").active_remote_executions == []


def test_release_failure_records_error() -> None:
    registry = _registry_with_cluster()
    allocator = ClusterAllocator(registry)
    scheduler = FederationScheduler(ClusterSelector(FederationDirectory(registry), RoutingEngine()))
    decision = scheduler.schedule("wf1", ["browser_agent"], 1)
    remote_execution = allocator.allocate(decision)

    released = allocator.release(remote_execution.remote_execution_id, success=False, error="boom")

    assert released.status == RemoteExecutionStatus.FAILED
    assert released.error == "boom"


def test_list_for_cluster() -> None:
    registry = _registry_with_cluster()
    allocator = ClusterAllocator(registry)
    scheduler = FederationScheduler(ClusterSelector(FederationDirectory(registry), RoutingEngine()))
    decision = scheduler.schedule("wf1", ["browser_agent"], 1)
    allocator.allocate(decision)
    assert len(allocator.list_for_cluster("c1")) == 1
    assert allocator.list_for_cluster("does-not-exist") == []


# -- WorkloadRouter -------------------------------------------------------------------------


def _router(registry: ClusterRegistry) -> WorkloadRouter:
    selector = ClusterSelector(FederationDirectory(registry), RoutingEngine())
    scheduler = FederationScheduler(selector)
    failover = FailoverManager(scheduler, selector, registry)
    allocator = ClusterAllocator(registry)
    return WorkloadRouter(scheduler, failover, allocator)


def test_workload_router_route_dispatches_and_allocates() -> None:
    registry = _registry_with_cluster()
    router = _router(registry)

    decision, remote_execution = router.route("wf1", ["browser_agent"], 1)

    assert decision.status == RoutingDecisionStatus.DISPATCHED
    assert remote_execution.status == RemoteExecutionStatus.RUNNING
    assert registry.get("c1").active_remote_executions == [remote_execution.remote_execution_id]


def test_workload_router_finish_success_closes_both_records() -> None:
    registry = _registry_with_cluster()
    router = _router(registry)
    decision, remote_execution = router.route("wf1", ["browser_agent"], 1)

    router.finish(decision.decision_id, remote_execution.remote_execution_id, success=True)

    assert registry.get("c1").active_remote_executions == []


def test_workload_router_finish_failure_marks_decision_failed() -> None:
    registry = _registry_with_cluster()
    router = _router(registry)
    decision, remote_execution = router.route("wf1", ["browser_agent"], 1)

    router.finish(decision.decision_id, remote_execution.remote_execution_id, success=False, error="boom")

    assert registry.get("c1").active_remote_executions == []


# -- FederationCoordinator ---------------------------------------------------------------------


class _FakeWorkflowDefinition:
    def __init__(self, steps: list[object]) -> None:
        self.steps = steps


class _FakeStep:
    def __init__(self, node_name: str) -> None:
        self.node_name = node_name


class _FakeWorkflow:
    def __init__(self, steps: list[str]) -> None:
        self.definition = _FakeWorkflowDefinition([_FakeStep(name) for name in steps])


class _FakeExecution:
    status = "completed"


class _FakeWorkflowService:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.resumed: list[str] = []

    def get(self, workflow_id: str) -> _FakeWorkflow:
        return _FakeWorkflow(["browser_agent"])

    async def execute(self, workflow_id: str, session_id: str | None = None) -> _FakeExecution:
        if self.fail:
            raise RuntimeError("boom")
        return _FakeExecution()

    async def resume(self, workflow_execution_id: str, session_id: str | None = None) -> _FakeExecution:
        self.resumed.append(workflow_execution_id)
        return _FakeExecution()


def test_federation_coordinator_routes_and_completes_on_success() -> None:
    registry = _registry_with_cluster()
    router = _router(registry)
    coordinator = FederationCoordinator(_FakeWorkflowService(), router)

    execution = asyncio.run(coordinator.execute("wf1", "session-1"))

    assert execution.status == "completed"
    assert registry.get("c1").active_remote_executions == []


def test_federation_coordinator_fails_decision_and_reraises_on_exception() -> None:
    registry = _registry_with_cluster()
    router = _router(registry)
    coordinator = FederationCoordinator(_FakeWorkflowService(fail=True), router)

    with pytest.raises(RuntimeError):
        asyncio.run(coordinator.execute("wf1", None))

    assert registry.get("c1").active_remote_executions == []


def test_federation_coordinator_raises_when_no_cluster_can_serve_the_workflow() -> None:
    router = _router(ClusterRegistry())  # no clusters registered at all
    coordinator = FederationCoordinator(_FakeWorkflowService(), router)

    from backend.federation.exceptions import NoEligibleClusterError

    with pytest.raises(NoEligibleClusterError):
        asyncio.run(coordinator.execute("wf1", None))


def test_federation_coordinator_forwards_resume_unchanged_via_getattr() -> None:
    """resume() is never wrapped — 'already-running work remains owned by its original cluster.'"""
    registry = _registry_with_cluster()
    router = _router(registry)
    inner = _FakeWorkflowService()
    coordinator = FederationCoordinator(inner, router)

    asyncio.run(coordinator.resume("we1", "session-1"))

    assert inner.resumed == ["we1"]
