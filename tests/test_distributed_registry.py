"""Tests for backend.distributed.registry: WorkerRegistry and DistributedCapabilityRegistry."""

import pytest

from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.distributed.exceptions import WorkerNotFoundError
from backend.distributed.models.worker_status import WorkerStatus
from backend.distributed.registry.capability_registry import (
    DistributedCapabilityRegistry,
)
from backend.distributed.registry.worker_registry import WorkerRegistry
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import InsightPilotState


class _FakeAgentNode(OrchestrationNode):
    name = "browser_agent"

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state


def _real_capability_registry() -> AgentCapabilityRegistry:
    graph_builder = GraphBuilder()
    graph_builder.add_node(_FakeAgentNode())
    graph_builder.set_entry_point("browser_agent")
    return AgentCapabilityRegistry(graph_builder)


# -- WorkerRegistry -------------------------------------------------------------------


def test_register_creates_an_online_worker() -> None:
    registry = WorkerRegistry()
    worker = registry.register("w1", "host-1", ["browser_agent"], maximum_parallel_tasks=2)
    assert worker.status == WorkerStatus.ONLINE
    assert worker.hostname == "host-1"
    assert worker.maximum_parallel_tasks == 2
    assert worker.last_heartbeat is not None


def test_register_is_idempotent_and_preserves_registered_at() -> None:
    registry = WorkerRegistry()
    first = registry.register("w1", "host-1", ["browser_agent"])
    second = registry.register("w1", "host-1-renamed", ["sql_agent"])
    assert second.registered_at == first.registered_at
    assert second.hostname == "host-1-renamed"
    assert second.supports("sql_agent")


def test_register_revives_a_previously_offline_worker() -> None:
    registry = WorkerRegistry()
    registry.register("w1", "host-1", ["browser_agent"])
    registry.set_status("w1", WorkerStatus.OFFLINE)
    revived = registry.register("w1", "host-1", ["browser_agent"])
    assert revived.status == WorkerStatus.ONLINE


def test_get_raises_for_unknown_worker() -> None:
    registry = WorkerRegistry()
    with pytest.raises(WorkerNotFoundError):
        registry.get("does-not-exist")


def test_list_by_status_and_list_supporting() -> None:
    registry = WorkerRegistry()
    registry.register("w1", "host-1", ["browser_agent"])
    registry.register("w2", "host-2", ["sql_agent"])
    registry.set_status("w2", WorkerStatus.OFFLINE)

    assert [w.worker_id for w in registry.list_by_status(WorkerStatus.ONLINE)] == ["w1"]
    assert [w.worker_id for w in registry.list_supporting("sql_agent")] == ["w2"]


def test_add_active_task_promotes_to_busy_at_capacity() -> None:
    registry = WorkerRegistry()
    registry.register("w1", "host-1", ["browser_agent"], maximum_parallel_tasks=1)
    updated = registry.add_active_task("w1", "a1")
    assert updated.status == WorkerStatus.BUSY
    assert updated.active_tasks == ["a1"]


def test_remove_active_task_demotes_back_to_online() -> None:
    registry = WorkerRegistry()
    registry.register("w1", "host-1", ["browser_agent"], maximum_parallel_tasks=1)
    registry.add_active_task("w1", "a1")
    updated = registry.remove_active_task("w1", "a1")
    assert updated.status == WorkerStatus.ONLINE
    assert updated.active_tasks == []


def test_record_heartbeat_refreshes_timestamp_and_revives_offline() -> None:
    registry = WorkerRegistry()
    registry.register("w1", "host-1", ["browser_agent"])
    registry.set_status("w1", WorkerStatus.FAILED)
    revived = registry.record_heartbeat("w1")
    assert revived.status == WorkerStatus.ONLINE


def test_remove_deregisters_a_worker() -> None:
    registry = WorkerRegistry()
    registry.register("w1", "host-1", ["browser_agent"])
    registry.remove("w1")
    with pytest.raises(WorkerNotFoundError):
        registry.get("w1")


# -- DistributedCapabilityRegistry ----------------------------------------------------


def test_is_recognized_reflects_the_real_live_graph() -> None:
    registry = DistributedCapabilityRegistry(_real_capability_registry())
    assert registry.is_recognized("browser_agent")
    assert not registry.is_recognized("not_a_real_agent")


def test_recognized_capabilities_filters_out_unknown_names() -> None:
    registry = DistributedCapabilityRegistry(_real_capability_registry())
    filtered = registry.recognized_capabilities(["browser_agent", "not_a_real_agent"])
    assert filtered == ["browser_agent"]
