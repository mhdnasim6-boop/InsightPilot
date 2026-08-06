"""Orchestration providers: event bus, graph builder, execution engine, orchestration service."""

from functools import lru_cache
from typing import Any

from fastapi import Depends
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from backend.agents.browser.services.browser_agent_service import BrowserAgentService
from backend.agents.executive_summary.services.executive_summary_service import (
    ExecutiveSummaryService,
)
from backend.agents.file.services.file_agent_service import FileAgentService
from backend.agents.planner.execution.planner_agent import PlannerAgent
from backend.agents.planner.services.execution_result_store import (
    PlannerAgentResultStore,
)
from backend.agents.planner.services.planner_agent_service import PlannerAgentService
from backend.agents.report.services.report_agent_service import ReportAgentService
from backend.agents.sql.services.sql_agent_service import SQLAgentService
from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.dependencies.browser_agent import get_browser_agent_service
from backend.dependencies.executive_summary import get_executive_summary_service
from backend.dependencies.file_agent import get_file_agent_service
from backend.dependencies.planner import (
    get_planner_agent_result_store,
    get_planner_service,
)
from backend.dependencies.report_agent import get_report_agent_service
from backend.dependencies.sql_agent import get_sql_agent_service
from backend.orchestration.events.bus import EventBus
from backend.orchestration.execution.engine import ExecutionEngine
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.graph.config import GraphConfig
from backend.orchestration.graph.default_graph import (
    approval_node_names,
    build_default_graph,
)
from backend.orchestration.nodes.planner_agent_node import PlannerAgentNode
from backend.services.orchestration_service import OrchestrationService
from backend.services.planner_service import PlannerService


@lru_cache
def get_event_bus() -> EventBus:
    """Return the process-wide event bus singleton.

    Shared across every execution so a listener registered once (e.g. at
    startup) observes every execution's events, not just one request's.
    """
    return EventBus()


@lru_cache
def get_checkpointer() -> BaseCheckpointSaver[Any]:
    """Return the process-wide LangGraph checkpointer singleton.

    An in-memory ``InMemorySaver`` — this phase implements no persistent
    checkpoint backend, matching ``CheckpointInterface``'s own
    "no implementation in this phase" scope from Phase 4. Cached (not
    just for correctness — see ``ExecutionEngine.resume()``'s own reuse
    of the exact ``CompiledGraph`` from ``run()``, which is what actually
    makes resume work across separate requests) so every compiled graph
    shares one checkpoint store. The custom serializer explicitly allows
    ``ExecutionStatus`` (an ``InsightPilotState`` field) through
    msgpack serialization instead of silently degrading to pickle or
    warning on every checkpoint write.
    """
    serde = JsonPlusSerializer(allowed_msgpack_modules=[("backend.orchestration.state.state", "ExecutionStatus")])
    return InMemorySaver(serde=serde)


@lru_cache
def get_execution_engine(event_bus: EventBus = Depends(get_event_bus)) -> ExecutionEngine:
    """Return the process-wide execution engine singleton.

    Cached like JobManager: in-flight executions must stay trackable
    (cancel/inspect) across requests, not just within the one that
    started them.
    """
    return ExecutionEngine(event_bus)


def get_graph_builder(
    event_bus: EventBus = Depends(get_event_bus),
    planner_service: PlannerService = Depends(get_planner_service),
    planner_agent_result_store: PlannerAgentResultStore = Depends(get_planner_agent_result_store),
    file_agent_service: FileAgentService = Depends(get_file_agent_service),
    sql_agent_service: SQLAgentService = Depends(get_sql_agent_service),
    browser_agent_service: BrowserAgentService = Depends(get_browser_agent_service),
    report_agent_service: ReportAgentService = Depends(get_report_agent_service),
    executive_summary_service: ExecutiveSummaryService = Depends(get_executive_summary_service),
) -> GraphBuilder:
    """Provide a GraphBuilder wired with the default Planner -> FileAgent -> SQLAgent ->
    BrowserAgent -> ReportAgent -> ExecutiveSummaryAgent -> End graph.

    Built here (DI wiring), not inside OrchestrationService — services
    never construct a GraphBuilder directly.

    ``PlannerAgent`` is handed this exact ``builder`` instance before
    ``build_default_graph()`` populates it — safe, not circular, because
    ``PlannerAgent`` only calls ``builder.export()`` lazily, at
    plan-generation time, by which point this function has already
    returned a fully populated builder (every node below is registered
    before this function's caller can reach an endpoint handler).
    """
    config = GraphConfig(interrupt_before=approval_node_names())
    builder = GraphBuilder(config=config, event_bus=event_bus)
    planner_agent_service = PlannerAgentService(PlannerAgent(planner_service, builder), planner_agent_result_store)
    return build_default_graph(
        builder,
        PlannerAgentNode(planner_agent_service),
        file_agent_service,
        sql_agent_service,
        browser_agent_service,
        report_agent_service,
        executive_summary_service,
    )


def get_orchestration_service(
    graph_builder: GraphBuilder = Depends(get_graph_builder),
    execution_engine: ExecutionEngine = Depends(get_execution_engine),
    checkpointer: BaseCheckpointSaver[Any] = Depends(get_checkpointer),
) -> OrchestrationService:
    """Provide the OrchestrationService — the only object that should be used for graph orchestration.

    Every approval interrupt point (``approval_node_names()``) is
    *always* configured on the compiled graph, with a real checkpointer
    behind it — whether a given run actually pauses there is a runtime
    policy decision made by ``PlanExecutor``, not something baked into
    graph compilation itself.
    """
    return OrchestrationService(graph_builder, execution_engine, checkpointer=checkpointer)


def get_capability_registry(
    graph_builder: GraphBuilder = Depends(get_graph_builder),
) -> AgentCapabilityRegistry:
    """Return an AgentCapabilityRegistry backed by the live GraphBuilder.

    Lives here (not in ``backend.dependencies.collaboration``) because
    its only real dependency is ``get_graph_builder`` itself — keeping it
    here lets ``get_planner_agent_service()`` below use it directly with
    no cross-module import, and lets
    ``backend.dependencies.collaboration`` import it one-way (that module
    already imports ``get_graph_builder`` from here too) instead of the
    two modules importing each other, which would be a real circular
    import: ``CollaborationService`` (built in that other module) is
    itself backed by an ``ExecutionService`` whose dispatcher would
    otherwise need ``get_planner_agent_service`` from *this* module.
    """
    return AgentCapabilityRegistry(graph_builder)


def get_planner_agent_service(
    planner_service: PlannerService = Depends(get_planner_service),
    graph_builder: GraphBuilder = Depends(get_graph_builder),
    result_store: PlannerAgentResultStore = Depends(get_planner_agent_result_store),
    capability_registry: AgentCapabilityRegistry = Depends(get_capability_registry),
) -> PlannerAgentService:
    """Provide PlannerAgentService for direct REST invocation of PlannerAgent.

    Shares ``graph_builder``/``result_store`` with whatever
    ``PlannerAgentNode`` this same request's ``get_graph_builder()`` call
    already wired into the graph (FastAPI de-duplicates a dependency
    within one request) — so a plan generated via this direct path and
    one generated by actually running the graph are both fetchable
    afterward through the same result store. ``capability_registry`` is
    the same registry ``CollaborationService.discover_capabilities()``
    itself wraps — see ``get_capability_registry()``'s own docstring for
    why Planner depends on the registry directly rather than the full
    service.
    """
    return PlannerAgentService(PlannerAgent(planner_service, graph_builder, capability_registry), result_store)
