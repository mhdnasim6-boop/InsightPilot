"""Tests for CollaborationService: the single public entry point tying the
coordinator, executor, capability registry, memory, and observability
together — mirrors test_execution_service.py's own construction/assertion
style.
"""

import asyncio

from pydantic import BaseModel

from backend.collaboration.coordinator.artifact_router import ArtifactRouter
from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.collaboration.coordinator.collaboration_coordinator import (
    CollaborationCoordinator,
)
from backend.collaboration.coordinator.delegation_engine import DelegationEngine
from backend.collaboration.coordinator.dependency_negotiator import DependencyNegotiator
from backend.collaboration.execution.collaboration_executor import CollaborationExecutor
from backend.collaboration.execution.subtask_manager import SubTaskManager
from backend.collaboration.messaging.message_bus import MessageBus
from backend.collaboration.models.collaboration_request import CollaborationRequest
from backend.collaboration.services.collaboration_service import CollaborationService
from backend.collaboration.stores.collaboration_store import CollaborationStore
from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore
from backend.execution.dispatcher.node_dispatcher import NodeDispatcher
from backend.execution.parallel.execution_pool import ExecutionPool
from backend.execution.scheduler.dag_scheduler import DAGScheduler
from backend.execution.services.execution_service import ExecutionService
from backend.execution.services.task_registry import ExecutionTaskRegistry
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.memory.store.memory_store import MemoryStore
from backend.observability.context import trace_context
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.stores.trace_store import TraceStore
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import InsightPilotState
from backend.planning.models.enums import PlanStatus
from backend.planning.models.step import ExecutionStep


class _Result(BaseModel):
    step_id: str
    status: str = "completed"
    execution_time: float = 0.01
    warnings: list[str] = []
    metadata: dict = {}


class _OkService:
    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> _Result:
        return _Result(step_id=step.step_id)


class _StubAgentNode(OrchestrationNode):
    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self._description = description

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state

    def metadata(self) -> dict[str, object]:
        return {"name": self.name, "description": self._description}


def _service(
    observability_service: ObservabilityService | None = None, memory_service: MemoryService | None = None
) -> CollaborationService:
    store = CollaborationStore()
    bus = MessageBus(store)
    coordinator = CollaborationCoordinator(
        store, bus, DelegationEngine(store, bus), DependencyNegotiator(store), ArtifactRouter()
    )
    dispatcher = NodeDispatcher()
    dispatcher.register("file_agent", _OkService())
    scheduler = DAGScheduler(dispatcher, ExecutionPool(), observability_service=observability_service)
    execution_service = ExecutionService(
        scheduler, ExecutionCheckpointStore(), ExecutionTaskRegistry(), observability_service, memory_service=memory_service
    )
    executor = CollaborationExecutor(coordinator, SubTaskManager(coordinator), execution_service)
    graph_builder = GraphBuilder()
    graph_builder.add_node(_StubAgentNode("file_agent", "Ingests files."))
    graph_builder.set_entry_point("file_agent")
    capability_registry = AgentCapabilityRegistry(graph_builder)
    return CollaborationService(coordinator, executor, capability_registry, bus, observability_service, memory_service)


def test_discover_capabilities_returns_registered_agents() -> None:
    service = _service()
    capabilities = service.discover_capabilities()
    assert [c.name for c in capabilities] == ["file_agent"]


def test_create_session_and_delegate_round_trip() -> None:
    service = _service()
    task = service.create_session(CollaborationRequest(goal="Analyze sales"))
    subtask = service.delegate(task.collaboration_id, "file_agent", "Ingest", {})
    fetched = service.get(task.collaboration_id)
    assert subtask.subtask_id in fetched.subtasks


def test_run_executes_to_completion() -> None:
    async def scenario() -> None:
        service = _service()
        task = service.create_session(CollaborationRequest(goal="Analyze sales"))
        service.delegate(task.collaboration_id, "file_agent", "Ingest", {})
        final = await service.run(task.collaboration_id)
        assert final.status == PlanStatus.COMPLETED

    asyncio.run(scenario())


def test_cancel_delegates_to_executor() -> None:
    service = _service()
    task = service.create_session(CollaborationRequest(goal="Analyze sales"))
    service.delegate(task.collaboration_id, "file_agent", "Ingest", {})
    cancelled = service.cancel(task.collaboration_id)
    assert cancelled.status == PlanStatus.CANCELLED


def test_terminal_session_is_remembered_via_memory_service() -> None:
    async def scenario() -> None:
        memory_service = MemoryService(store=MemoryStore())
        service = _service(memory_service=memory_service)
        task = service.create_session(CollaborationRequest(goal="Analyze sales for Q1"))
        service.delegate(task.collaboration_id, "file_agent", "Ingest", {})

        await service.run(task.collaboration_id)

        memories = memory_service.list_all()
        collaboration_memories = [m for m in memories if m.memory_type == MemoryType.COLLABORATION]
        assert len(collaboration_memories) == 1
        assert collaboration_memories[0].content["collaboration_id"] == task.collaboration_id
        assert collaboration_memories[0].content["status"] == "completed"

    asyncio.run(scenario())


def test_non_terminal_session_is_not_remembered() -> None:
    memory_service = MemoryService(store=MemoryStore())
    service = _service(memory_service=memory_service)
    service.create_session(CollaborationRequest(goal="Analyze sales"))
    assert memory_service.list_all() == []


def test_each_wave_produces_a_real_observability_trace() -> None:
    """CollaborationExecutor dispatches every wave through the real ExecutionService,
    so every subtask still produces its own full ExecutionTrace — proven here by
    inspecting the trace for the wave's own (freshly generated) plan_id.
    """

    async def scenario() -> None:
        observability_service = ObservabilityService(TraceStore())
        service = _service(observability_service=observability_service)
        task = service.create_session(CollaborationRequest(goal="Analyze sales"))
        service.delegate(task.collaboration_id, "file_agent", "Ingest", {})

        await service.run(task.collaboration_id)

        traces = observability_service.list_traces()
        assert len(traces) == 1
        assert traces[0].status == PlanStatus.COMPLETED
        assert len(traces[0].agent_traces) == 1
        assert traces[0].agent_traces[0].agent_name == "file_agent"

    asyncio.run(scenario())


def test_collaboration_service_traces_its_own_operations_when_a_trace_is_active() -> None:
    """CollaborationService reuses ObservabilityService.record_tool_trace() exactly like
    MemoryService — a no-op outside any active trace, but recorded when one is active
    (e.g. this service being invoked from within an already-traced flow).
    """
    observability_service = ObservabilityService(TraceStore())
    service = _service(observability_service=observability_service)
    trace_id = observability_service.start_trace("outer-plan-1")

    with trace_context(trace_id):
        service.create_session(CollaborationRequest(goal="Analyze sales"))

    trace = observability_service.get_trace(trace_id)
    assert any(t.tool_name == "collaboration.create_session" for t in trace.tool_traces)


def test_history_returns_messages_delegations_and_exchanges() -> None:
    service = _service()
    task = service.create_session(CollaborationRequest(goal="Analyze sales"))
    service.delegate(task.collaboration_id, "file_agent", "Ingest", {})
    history = service.history(task.collaboration_id)
    assert len(history["messages"]) == 1
    assert len(history["delegations"]) == 1
    assert history["artifact_exchanges"] == []
    assert history["negotiations"] == []


def test_statistics_aggregates_across_sessions() -> None:
    service = _service()
    first = service.create_session(CollaborationRequest(goal="Session one"))
    service.delegate(first.collaboration_id, "file_agent", "Ingest", {})
    service.create_session(CollaborationRequest(goal="Session two"))

    stats = service.statistics()

    assert stats.total_sessions == 2
    assert stats.total_subtasks == 1
    assert stats.by_status[PlanStatus.DRAFT.value] == 2
    assert stats.average_subtasks_per_session == 0.5


def test_list_sessions_returns_every_tracked_session() -> None:
    service = _service()
    service.create_session(CollaborationRequest(goal="One"))
    service.create_session(CollaborationRequest(goal="Two"))
    assert len(service.list_sessions()) == 2
