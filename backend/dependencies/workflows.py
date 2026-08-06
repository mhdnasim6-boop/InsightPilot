"""Workflow Engine providers: every collaborator WorkflowService composes,
each already-provided elsewhere in this codebase and reused here — no
new business logic, only wiring.

``get_workflow_store()`` is the one genuinely stateful, cached singleton
this package introduces (mirrors ``get_tool_registry()``); every other
provider below (including ``get_workflow_service`` itself) is left
uncached, mirroring ``get_execution_service``'s own precedent exactly:
all cross-request state lives in the cached store/registries these
functions are handed, not in the thin service wrappers themselves.
"""

from functools import lru_cache
from typing import Any

from fastapi import Depends

from backend.adaptive.services.adaptive_planning_service import AdaptivePlanningService
from backend.approval.services.approval_service import ApprovalService
from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.collaboration.services.collaboration_service import CollaborationService
from backend.dependencies.adaptive import get_adaptive_planning_service
from backend.dependencies.approval import get_approval_service
from backend.dependencies.collaboration import get_collaboration_service
from backend.dependencies.execution import get_execution_service
from backend.dependencies.federation import get_workload_router
from backend.dependencies.memory import get_memory_service
from backend.dependencies.observability import get_observability_service
from backend.dependencies.orchestration import get_capability_registry
from backend.dependencies.planner import get_planner_service
from backend.dependencies.planning import get_planning_service
from backend.dependencies.plugins import get_plugin_registry
from backend.dependencies.realtime import get_realtime_service
from backend.dependencies.reflection import get_reflection_service
from backend.dependencies.tools import get_tool_registry
from backend.execution.services.execution_service import ExecutionService
from backend.federation.coordination.federation_coordinator import (
    FederationCoordinator,
)
from backend.federation.coordination.workload_router import WorkloadRouter
from backend.memory.services.memory_service import MemoryService
from backend.observability.services.observability_service import ObservabilityService
from backend.plugins.registry.plugin_registry import PluginRegistry
from backend.realtime.publishers.workflow_publisher import (
    RealtimePublishingWorkflowOptimizer,
    RealtimePublishingWorkflowService,
)
from backend.realtime.services.realtime_service import RealtimeService
from backend.reflection.services.reflection_service import ReflectionService
from backend.services.planner_service import PlannerService
from backend.services.planning_service import PlanningService
from backend.tools.registry.tool_registry import ToolRegistry
from backend.workflows.coordination.collaboration_manager import (
    WorkflowCollaborationManager,
)
from backend.workflows.coordination.dependency_graph import WorkflowDependencyGraph
from backend.workflows.coordination.execution_coordinator import ExecutionCoordinator
from backend.workflows.coordination.resource_allocator import ResourceAllocator
from backend.workflows.execution.workflow_dispatcher import WorkflowDispatcher
from backend.workflows.execution.workflow_engine import WorkflowEngine
from backend.workflows.execution.workflow_scheduler import WorkflowScheduler
from backend.workflows.planner.workflow_builder import WorkflowBuilder
from backend.workflows.planner.workflow_optimizer import WorkflowOptimizer
from backend.workflows.planner.workflow_validator import WorkflowValidator
from backend.workflows.services.workflow_service import WorkflowService, WorkflowStore


@lru_cache
def get_workflow_store() -> WorkflowStore:
    """Return the process-wide WorkflowStore singleton — every Workflow/WorkflowExecution lives here."""
    return WorkflowStore()


@lru_cache
def get_workflow_dependency_graph() -> WorkflowDependencyGraph:
    """Return the process-wide WorkflowDependencyGraph singleton. Stateless — cached for identity reuse."""
    return WorkflowDependencyGraph()


@lru_cache
def get_resource_allocator() -> ResourceAllocator:
    """Return the process-wide ResourceAllocator singleton — bounds concurrent workflow executions."""
    return ResourceAllocator()


def get_workflow_dispatcher(
    capability_registry: AgentCapabilityRegistry = Depends(get_capability_registry),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
    plugin_registry: PluginRegistry = Depends(get_plugin_registry),
) -> WorkflowDispatcher:
    """Provide a WorkflowDispatcher wired to the real, live agent/tool/plugin registries."""
    return WorkflowDispatcher(capability_registry, tool_registry, plugin_registry)


def get_workflow_collaboration_manager(
    collaboration_service: CollaborationService = Depends(get_collaboration_service),
) -> WorkflowCollaborationManager:
    """Provide a WorkflowCollaborationManager wrapping the real CollaborationService."""
    return WorkflowCollaborationManager(collaboration_service)


def get_execution_coordinator(
    dispatcher: WorkflowDispatcher = Depends(get_workflow_dispatcher),
    dependency_graph: WorkflowDependencyGraph = Depends(get_workflow_dependency_graph),
) -> ExecutionCoordinator:
    """Provide an ExecutionCoordinator — dynamic agent validation + dependency ordering + plan construction."""
    return ExecutionCoordinator(dispatcher, dependency_graph)


def get_workflow_builder(
    dispatcher: WorkflowDispatcher = Depends(get_workflow_dispatcher),
    planner_service: PlannerService = Depends(get_planner_service),
) -> WorkflowBuilder:
    """Provide a WorkflowBuilder wired to the real PlannerService for objective-based creation."""
    return WorkflowBuilder(dispatcher, planner_service)


def get_workflow_validator(
    planning_service: PlanningService = Depends(get_planning_service),
) -> WorkflowValidator:
    """Provide a WorkflowValidator delegating to the real PlanningService.validate()."""
    return WorkflowValidator(planning_service)


def get_workflow_optimizer(
    adaptive_planning_service: AdaptivePlanningService = Depends(get_adaptive_planning_service),
    planning_service: PlanningService = Depends(get_planning_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> WorkflowOptimizer:
    """Provide a WorkflowOptimizer delegating to AdaptivePlanningService + the real PlanOptimizer.

    Wrapped in ``RealtimePublishingWorkflowOptimizer`` (Phase 37) —
    publishes OptimizationGenerated after every ``adaptive_optimize()``
    with no change to ``WorkflowOptimizer`` itself.
    """
    optimizer: Any = RealtimePublishingWorkflowOptimizer(
        WorkflowOptimizer(adaptive_planning_service, planning_service), realtime_service
    )
    return optimizer


def get_workflow_scheduler(
    resource_allocator: ResourceAllocator = Depends(get_resource_allocator),
) -> WorkflowScheduler:
    """Provide a WorkflowScheduler bounding concurrent workflow executions."""
    return WorkflowScheduler(resource_allocator)


def get_workflow_engine(
    execution_coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
    validator: WorkflowValidator = Depends(get_workflow_validator),
    optimizer: WorkflowOptimizer = Depends(get_workflow_optimizer),
    execution_service: ExecutionService = Depends(get_execution_service),
    scheduler: WorkflowScheduler = Depends(get_workflow_scheduler),
    observability_service: ObservabilityService = Depends(get_observability_service),
    reflection_service: ReflectionService = Depends(get_reflection_service),
) -> WorkflowEngine:
    """Provide the WorkflowEngine — the highest orchestration layer, entirely delegating to
    the real PlanValidator/PlanOptimizer/AdaptivePlanningService/ExecutionService."""
    return WorkflowEngine(
        execution_coordinator, validator, optimizer, execution_service, scheduler,
        observability_service, reflection_service,
    )


def get_workflow_service(
    store: WorkflowStore = Depends(get_workflow_store),
    builder: WorkflowBuilder = Depends(get_workflow_builder),
    validator: WorkflowValidator = Depends(get_workflow_validator),
    optimizer: WorkflowOptimizer = Depends(get_workflow_optimizer),
    engine: WorkflowEngine = Depends(get_workflow_engine),
    execution_coordinator: ExecutionCoordinator = Depends(get_execution_coordinator),
    dependency_graph: WorkflowDependencyGraph = Depends(get_workflow_dependency_graph),
    dispatcher: WorkflowDispatcher = Depends(get_workflow_dispatcher),
    collaboration_manager: WorkflowCollaborationManager = Depends(get_workflow_collaboration_manager),
    execution_service: ExecutionService = Depends(get_execution_service),
    approval_service: ApprovalService = Depends(get_approval_service),
    memory_service: MemoryService = Depends(get_memory_service),
    observability_service: ObservabilityService = Depends(get_observability_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
    workload_router: WorkloadRouter = Depends(get_workload_router),
) -> WorkflowService:
    """Provide the WorkflowService — the only object anything should use for workflows.

    Deliberately uncached, mirroring ``get_execution_service``: every
    piece of state that must survive across requests already lives in
    the cached ``WorkflowStore``/``ToolRegistry``/``PluginRegistry``/
    ``ExecutionCheckpointStore``/etc. this function's own dependencies
    are built from — rebuilding this thin composition on every request
    is cheap and correct.

    Wrapped in ``RealtimePublishingWorkflowService`` (Phase 37) — publishes
    WorkflowStarted/Completed/Failed around ``execute()``/``resume()``/
    ``cancel()`` — and then in ``FederationCoordinator`` (Phase 39,
    outermost) — routes each ``execute()`` call to a credited cluster
    (always the local one in a single-cluster deployment) before
    delegating — with no change to ``WorkflowService`` itself either way.
    """
    realtime_wrapped: Any = RealtimePublishingWorkflowService(
        WorkflowService(
            store=store, builder=builder, validator=validator, optimizer=optimizer, engine=engine,
            execution_coordinator=execution_coordinator, dependency_graph=dependency_graph, dispatcher=dispatcher,
            collaboration_manager=collaboration_manager, execution_service=execution_service,
            approval_service=approval_service, memory_service=memory_service,
            observability_service=observability_service,
        ),
        realtime_service,
    )
    service: Any = FederationCoordinator(realtime_wrapped, workload_router)
    return service
