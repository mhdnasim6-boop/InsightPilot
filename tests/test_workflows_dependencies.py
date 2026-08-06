"""Tests for backend.dependencies.workflows: singleton caching for the
genuinely stateful providers, and that each DI provider function
constructs the right, correctly-wired object type.

Deliberately does not resolve the real app's own ``get_graph_builder()``
bare here — that function's own ``Depends()``-defaulted parameters only
resolve correctly through FastAPI's real request handling (the same
documented gotcha ``test_mcp_dependencies.py`` first caught: calling a
``Depends(...)``-defaulted provider bare binds the literal ``Depends``
marker object, not a real dependency). A small, real, local
``GraphBuilder`` (the same fake-node pattern every other
``tests/test_workflows_*.py`` file already uses) is enough to prove each
DI *function itself* wires correctly; the full chain against the real
app's own default graph is separately proven by
tests/test_api_v1_workflows.py's real HTTP round trips — the same
division of labor test_mcp_dependencies.py uses for its own (much
shallower) chain. Nothing here needs a ``resolve_workflow_service()``-
style manual chain either: unlike Security's AuthenticationMiddleware or
Operations' StartupManager, nothing constructs a WorkflowService outside
a real FastAPI request.
"""

from backend.adaptive.services.adaptive_planning_service import AdaptivePlanningService
from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.approval.stores.approval_store import ApprovalStore
from backend.approval.stores.execution_history_store import ExecutionHistoryStore
from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.dependencies.plugins import get_plugin_registry
from backend.dependencies.realtime import resolve_realtime_service
from backend.dependencies.tools import get_tool_registry
from backend.dependencies.workflows import (
    get_execution_coordinator,
    get_resource_allocator,
    get_workflow_dependency_graph,
    get_workflow_dispatcher,
    get_workflow_engine,
    get_workflow_optimizer,
    get_workflow_scheduler,
    get_workflow_store,
    get_workflow_validator,
)
from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore
from backend.execution.dispatcher.node_dispatcher import NodeDispatcher
from backend.execution.scheduler.dag_scheduler import DAGScheduler
from backend.execution.services.execution_service import ExecutionService
from backend.execution.services.task_registry import ExecutionTaskRegistry
from backend.memory.exporters.json_exporter import JSONMemoryExporter
from backend.memory.exporters.markdown_exporter import MarkdownMemoryExporter
from backend.memory.retrieval.retrieval_engine import RetrievalEngine
from backend.memory.services.memory_service import MemoryService
from backend.memory.store.memory_store import MemoryStore
from backend.memory.summarization.memory_summarizer import MemorySummarizer
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.stores.trace_store import TraceStore
from backend.orchestration.events.bus import EventBus
from backend.orchestration.execution.engine import ExecutionEngine
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.base import OrchestrationNode
from backend.orchestration.state.state import InsightPilotState
from backend.planning.events.bus import PlanEventBus
from backend.planning.executor.executor import PlanExecutor
from backend.planning.optimizer.default import DefaultPlanOptimizer
from backend.planning.validator.validator import PlanValidator
from backend.reflection.services.reflection_service import ReflectionService
from backend.services.orchestration_service import OrchestrationService
from backend.services.planning_service import PlanningService
from backend.workflows.coordination.execution_coordinator import ExecutionCoordinator
from backend.workflows.execution.workflow_dispatcher import WorkflowDispatcher
from backend.workflows.execution.workflow_engine import WorkflowEngine
from backend.workflows.execution.workflow_scheduler import WorkflowScheduler
from backend.workflows.planner.workflow_optimizer import WorkflowOptimizer
from backend.workflows.planner.workflow_validator import WorkflowValidator
from backend.workflows.services.workflow_service import WorkflowStore


class _FakeAgentNode(OrchestrationNode):
    name = "fake_agent"

    async def execute(self, state: InsightPilotState) -> InsightPilotState:
        return state


def _capability_registry_and_planning_service() -> tuple[AgentCapabilityRegistry, PlanningService, AdaptivePlanningService]:
    graph_builder = GraphBuilder()
    graph_builder.add_node(_FakeAgentNode())
    graph_builder.set_entry_point("fake_agent")
    orchestration_service = OrchestrationService(graph_builder, ExecutionEngine(EventBus()))
    capability_registry = AgentCapabilityRegistry(graph_builder)

    memory_service = MemoryService(
        store=MemoryStore(), retrieval_engine=RetrievalEngine(), summarizer=MemorySummarizer(),
        json_exporter=JSONMemoryExporter(), markdown_exporter=MarkdownMemoryExporter(),
    )
    observability_service = ObservabilityService(TraceStore())
    reflection_service = ReflectionService(memory_service, observability_service)
    adaptive_planning_service = AdaptivePlanningService(memory_service, reflection_service, observability_service)
    approval_service = ApprovalService(ApprovalStore(), ExecutionHistoryStore())
    executor = PlanExecutor(PlanEventBus(), approval_service, ApprovalPolicyService(), observability_service)
    planning_service = PlanningService(
        PlanValidator(), DefaultPlanOptimizer(), executor, orchestration_service, PlanEventBus(),
    )
    return capability_registry, planning_service, adaptive_planning_service


def test_get_workflow_store_is_a_singleton() -> None:
    assert get_workflow_store() is get_workflow_store()


def test_get_workflow_dependency_graph_is_a_singleton() -> None:
    assert get_workflow_dependency_graph() is get_workflow_dependency_graph()


def test_get_resource_allocator_is_a_singleton() -> None:
    assert get_resource_allocator() is get_resource_allocator()


def test_workflow_store_returned_by_the_provider_is_the_real_type() -> None:
    assert isinstance(get_workflow_store(), WorkflowStore)


def test_get_workflow_dispatcher_wires_the_given_registries() -> None:
    capability_registry, _, _ = _capability_registry_and_planning_service()
    tool_registry = get_tool_registry()
    plugin_registry = get_plugin_registry(tool_registry=tool_registry, realtime_service=resolve_realtime_service())

    dispatcher = get_workflow_dispatcher(
        capability_registry=capability_registry, tool_registry=tool_registry, plugin_registry=plugin_registry,
    )

    assert isinstance(dispatcher, WorkflowDispatcher)
    assert dispatcher.discover_agent_names() == {"fake_agent"}


def test_get_execution_coordinator_returns_the_real_type() -> None:
    capability_registry, _, _ = _capability_registry_and_planning_service()
    tool_registry = get_tool_registry()
    dispatcher = get_workflow_dispatcher(
        capability_registry=capability_registry, tool_registry=tool_registry,
        plugin_registry=get_plugin_registry(tool_registry=tool_registry, realtime_service=resolve_realtime_service()),
    )
    coordinator = get_execution_coordinator(dispatcher=dispatcher, dependency_graph=get_workflow_dependency_graph())
    assert isinstance(coordinator, ExecutionCoordinator)


def test_get_workflow_validator_and_optimizer_return_the_real_types() -> None:
    _, planning_service, adaptive_planning_service = _capability_registry_and_planning_service()
    validator = get_workflow_validator(planning_service=planning_service)
    optimizer = get_workflow_optimizer(
        adaptive_planning_service=adaptive_planning_service, planning_service=planning_service,
        realtime_service=resolve_realtime_service(),
    )
    assert isinstance(validator, WorkflowValidator)
    # Phase 37: get_workflow_optimizer() wraps the real WorkflowOptimizer in
    # RealtimePublishingWorkflowOptimizer (publishes OptimizationGenerated) — same
    # "decorator satisfies the contract, not the class" shape as every other wrapped
    # provider in this phase; see test_security_dependencies.py's own equivalent.
    assert not isinstance(optimizer, WorkflowOptimizer)
    assert hasattr(optimizer, "adaptive_optimize")
    assert hasattr(optimizer, "structural_optimize")


def test_get_workflow_scheduler_returns_the_real_type() -> None:
    scheduler = get_workflow_scheduler(resource_allocator=get_resource_allocator())
    assert isinstance(scheduler, WorkflowScheduler)


def test_get_workflow_engine_returns_the_real_type() -> None:
    capability_registry, planning_service, adaptive_planning_service = _capability_registry_and_planning_service()
    tool_registry = get_tool_registry()
    dispatcher = get_workflow_dispatcher(
        capability_registry=capability_registry, tool_registry=tool_registry,
        plugin_registry=get_plugin_registry(tool_registry=tool_registry, realtime_service=resolve_realtime_service()),
    )
    coordinator = get_execution_coordinator(dispatcher=dispatcher, dependency_graph=get_workflow_dependency_graph())
    validator = get_workflow_validator(planning_service=planning_service)
    optimizer = get_workflow_optimizer(
        adaptive_planning_service=adaptive_planning_service, planning_service=planning_service,
        realtime_service=resolve_realtime_service(),
    )
    # Constructed directly, not via get_execution_service()/get_observability_service()/
    # get_reflection_service() — each is Depends()-defaulted and (for the latter two)
    # @lru_cache'd, unsafe to call bare outside a real request for the same reason this
    # file avoids get_graph_builder() bare. A real, working instance of each is all
    # get_workflow_engine() itself needs to prove its own wiring is correct.
    observability_service = ObservabilityService(TraceStore())
    reflection_service = ReflectionService(MemoryService(
        store=MemoryStore(), retrieval_engine=RetrievalEngine(), summarizer=MemorySummarizer(),
        json_exporter=JSONMemoryExporter(), markdown_exporter=MarkdownMemoryExporter(),
    ), observability_service)
    execution_service = ExecutionService(
        DAGScheduler(NodeDispatcher()), ExecutionCheckpointStore(), ExecutionTaskRegistry(),
    )
    engine = get_workflow_engine(
        execution_coordinator=coordinator, validator=validator, optimizer=optimizer,
        execution_service=execution_service,
        scheduler=get_workflow_scheduler(resource_allocator=get_resource_allocator()),
        observability_service=observability_service, reflection_service=reflection_service,
    )
    assert isinstance(engine, WorkflowEngine)
