"""Tests for backend.dependencies.distributed: singleton caching and that each
DI provider function constructs the right, correctly-wired object type.

Deliberately does not resolve the real app's own ``get_graph_builder()``
bare here for the capability-registry chain — a small, real, local
``GraphBuilder`` (the same fake-node pattern
``test_workflows_dependencies.py`` already uses) is enough to prove each
DI *function itself* wires correctly; the full chain against the real
app's own default graph is separately proven by
``tests/test_api_v1_distributed.py``'s real HTTP round trips.
"""

from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.dependencies.distributed import (
    get_dispatch_scheduler,
    get_distributed_capability_registry,
    get_distributed_execution_service,
    get_heartbeat_manager,
    get_lease_manager,
    get_load_balancer,
    get_retry_queue,
    get_task_queue,
    get_task_recovery,
    get_worker_monitor,
    get_worker_recovery,
    get_worker_registry,
    get_worker_selector,
)
from backend.dependencies.execution_checkpoint import get_execution_checkpoint_store
from backend.distributed.heartbeat.heartbeat_manager import HeartbeatManager
from backend.distributed.heartbeat.worker_monitor import WorkerMonitor
from backend.distributed.recovery.task_recovery import TaskRecovery
from backend.distributed.recovery.worker_recovery import WorkerRecovery
from backend.distributed.registry.capability_registry import (
    DistributedCapabilityRegistry,
)
from backend.distributed.scheduler.dispatch_scheduler import DispatchScheduler
from backend.distributed.scheduler.worker_selector import WorkerSelector
from backend.distributed.services.distributed_execution_service import (
    DistributedExecutionService,
)
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import InsightPilotState


class _FakeAgentNode(OrchestrationNode):
    name = "browser_agent"

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state


def _real_capability_registry() -> DistributedCapabilityRegistry:
    graph_builder = GraphBuilder()
    graph_builder.add_node(_FakeAgentNode())
    graph_builder.set_entry_point("browser_agent")
    return get_distributed_capability_registry(agent_capability_registry=AgentCapabilityRegistry(graph_builder))


def test_stateful_singletons_are_cached_across_calls() -> None:
    assert get_worker_registry() is get_worker_registry()
    assert get_lease_manager() is get_lease_manager()
    assert get_task_queue() is get_task_queue()
    assert get_retry_queue() is get_retry_queue()
    assert get_load_balancer() is get_load_balancer()


def test_heartbeat_manager_and_worker_monitor_are_cached_and_share_the_registry() -> None:
    manager = get_heartbeat_manager(worker_registry=get_worker_registry(), lease_manager=get_lease_manager())
    assert manager is get_heartbeat_manager(worker_registry=get_worker_registry(), lease_manager=get_lease_manager())
    assert isinstance(manager, HeartbeatManager)

    monitor = get_worker_monitor(worker_registry=get_worker_registry())
    assert monitor is get_worker_monitor(worker_registry=get_worker_registry())
    assert isinstance(monitor, WorkerMonitor)


def test_get_distributed_capability_registry_returns_the_real_type() -> None:
    registry = _real_capability_registry()
    assert isinstance(registry, DistributedCapabilityRegistry)
    assert registry.is_recognized("browser_agent")


def test_get_worker_selector_returns_the_real_type() -> None:
    selector = get_worker_selector(
        worker_registry=get_worker_registry(),
        capability_registry=_real_capability_registry(),
        load_balancer=get_load_balancer(),
    )
    assert isinstance(selector, WorkerSelector)


def test_get_dispatch_scheduler_returns_the_real_type() -> None:
    selector = get_worker_selector(
        worker_registry=get_worker_registry(), capability_registry=_real_capability_registry(),
        load_balancer=get_load_balancer(),
    )
    scheduler = get_dispatch_scheduler(
        worker_selector=selector, worker_registry=get_worker_registry(),
        lease_manager=get_lease_manager(), task_queue=get_task_queue(),
    )
    assert isinstance(scheduler, DispatchScheduler)


def test_get_task_recovery_and_worker_recovery_return_the_real_types() -> None:
    task_recovery = get_task_recovery(
        task_queue=get_task_queue(), retry_queue=get_retry_queue(), lease_manager=get_lease_manager(),
        worker_registry=get_worker_registry(), checkpoint_store=get_execution_checkpoint_store(),
    )
    assert isinstance(task_recovery, TaskRecovery)

    worker_recovery = get_worker_recovery(task_queue=get_task_queue(), task_recovery=task_recovery)
    assert isinstance(worker_recovery, WorkerRecovery)


def test_get_distributed_execution_service_returns_the_real_type() -> None:
    capability_registry = _real_capability_registry()
    worker_selector = get_worker_selector(
        worker_registry=get_worker_registry(), capability_registry=capability_registry, load_balancer=get_load_balancer()
    )
    dispatch_scheduler = get_dispatch_scheduler(
        worker_selector=worker_selector, worker_registry=get_worker_registry(),
        lease_manager=get_lease_manager(), task_queue=get_task_queue(),
    )
    task_recovery = get_task_recovery(
        task_queue=get_task_queue(), retry_queue=get_retry_queue(), lease_manager=get_lease_manager(),
        worker_registry=get_worker_registry(), checkpoint_store=get_execution_checkpoint_store(),
    )
    worker_recovery = get_worker_recovery(task_queue=get_task_queue(), task_recovery=task_recovery)

    service = get_distributed_execution_service(
        worker_registry=get_worker_registry(), capability_registry=capability_registry,
        dispatch_scheduler=dispatch_scheduler, task_queue=get_task_queue(), retry_queue=get_retry_queue(),
        heartbeat_manager=get_heartbeat_manager(worker_registry=get_worker_registry(), lease_manager=get_lease_manager()),
        worker_monitor=get_worker_monitor(worker_registry=get_worker_registry()),
        worker_recovery=worker_recovery,
    )

    assert isinstance(service, DistributedExecutionService)
