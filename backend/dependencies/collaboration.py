"""Collaboration layer providers: store, message bus, coordinator, a dedicated
collaboration-scoped ExecutionService, executor, and the top-level
CollaborationService.

``get_collaboration_node_dispatcher()`` deliberately registers only the
five *worker* agents (File/SQL/Browser/Report/ExecutiveSummary) — never
``planner`` — sharing the same cached ``ExecutionPool``/
``ExecutionCheckpointStore``/``ExecutionTaskRegistry``/``ApprovalService``/
``ObservabilityService`` singletons ``backend.dependencies.execution``
already uses, just wired into a second, collaboration-scoped
``DAGScheduler``/``ExecutionService`` pair. This is not duplicated
execution logic — every class involved (``DAGScheduler``,
``ExecutionService``) is reused unmodified; only the *dispatcher's own
registrations* differ, because a collaboration SubTask is never
delegated to "planner" itself (Planner is queried once for capabilities
via ``discover_capabilities()``, never assigned a SubTask).

That exclusion is also why ``PlannerAgent`` (see
``backend.dependencies.orchestration.get_planner_agent_service``) depends
on ``AgentCapabilityRegistry`` directly rather than the full
``CollaborationService`` defined here: this module's own
``ExecutionService`` would otherwise need ``get_planner_agent_service``
registered in its dispatcher (like ``backend.dependencies.execution``'s
own dispatcher does) to run a "planner" SubTask, which would cycle
right back to ``get_planner_agent_service`` itself.
``get_capability_registry()`` lives in ``backend.dependencies.orchestration``
instead (its only real dependency is ``get_graph_builder``, defined
there) precisely so both modules can share it without importing each
other.

``CollaborationService`` itself is left uncached, mirroring
``ExecutionService``'s own reasoning exactly (see
``backend.dependencies.execution``'s docstring) — it depends on
``CollaborationExecutor``, which itself depends on an uncached
``ExecutionService``, so caching anything built from it would silently
never hit its cache. All real state instead lives in the independently
cached ``CollaborationStore``.
"""

from functools import lru_cache

from fastapi import Depends

from backend.agents.browser.services.browser_agent_service import BrowserAgentService
from backend.agents.executive_summary.services.executive_summary_service import (
    ExecutiveSummaryService,
)
from backend.agents.file.services.file_agent_service import FileAgentService
from backend.agents.report.services.report_agent_service import ReportAgentService
from backend.agents.sql.services.sql_agent_service import SQLAgentService
from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
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
from backend.collaboration.services.collaboration_service import CollaborationService
from backend.collaboration.stores.collaboration_store import CollaborationStore
from backend.dependencies.approval import (
    get_approval_policy_service,
    get_approval_service,
)
from backend.dependencies.browser_agent import get_browser_agent_service
from backend.dependencies.execution import (
    get_execution_checkpoint_store,
    get_execution_pool,
    get_execution_task_registry,
    get_progress_tracker,
)
from backend.dependencies.executive_summary import get_executive_summary_service
from backend.dependencies.file_agent import get_file_agent_service
from backend.dependencies.memory import get_memory_service
from backend.dependencies.observability import get_observability_service
from backend.dependencies.orchestration import get_capability_registry
from backend.dependencies.report_agent import get_report_agent_service
from backend.dependencies.sql_agent import get_sql_agent_service
from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore
from backend.execution.dispatcher.node_dispatcher import NodeDispatcher
from backend.execution.parallel.execution_pool import ExecutionPool
from backend.execution.progress.progress_tracker import ProgressTracker
from backend.execution.scheduler.dag_scheduler import DAGScheduler
from backend.execution.services.execution_service import ExecutionService
from backend.execution.services.task_registry import ExecutionTaskRegistry
from backend.memory.services.memory_service import MemoryService
from backend.observability.services.observability_service import ObservabilityService


@lru_cache
def get_collaboration_store() -> CollaborationStore:
    """Return the process-wide CollaborationStore singleton."""
    return CollaborationStore()


def get_message_bus(store: CollaborationStore = Depends(get_collaboration_store)) -> MessageBus:
    """Return a MessageBus over the shared CollaborationStore."""
    return MessageBus(store)


def get_collaboration_coordinator(
    store: CollaborationStore = Depends(get_collaboration_store),
    message_bus: MessageBus = Depends(get_message_bus),
) -> CollaborationCoordinator:
    """Return a CollaborationCoordinator wired with the shared store/message bus."""
    return CollaborationCoordinator(
        store, message_bus, DelegationEngine(store, message_bus), DependencyNegotiator(store), ArtifactRouter()
    )


def get_collaboration_node_dispatcher(
    file_agent_service: FileAgentService = Depends(get_file_agent_service),
    sql_agent_service: SQLAgentService = Depends(get_sql_agent_service),
    browser_agent_service: BrowserAgentService = Depends(get_browser_agent_service),
    report_agent_service: ReportAgentService = Depends(get_report_agent_service),
    executive_summary_service: ExecutiveSummaryService = Depends(get_executive_summary_service),
) -> NodeDispatcher:
    """Return a NodeDispatcher registering every worker agent SubTasks may be delegated to.

    Deliberately excludes ``planner`` — see this module's own docstring
    for why (breaks a real DI cycle, and Planner is never a collaboration
    SubTask's assignee).
    """
    dispatcher = NodeDispatcher()
    dispatcher.register("file_agent", file_agent_service)
    dispatcher.register("sql_agent", sql_agent_service)
    dispatcher.register("browser_agent", browser_agent_service)
    dispatcher.register("report_agent", report_agent_service)
    dispatcher.register("executive_summary_agent", executive_summary_service)
    return dispatcher


def get_collaboration_dag_scheduler(
    dispatcher: NodeDispatcher = Depends(get_collaboration_node_dispatcher),
    pool: ExecutionPool = Depends(get_execution_pool),
    approval_service: ApprovalService = Depends(get_approval_service),
    approval_policy_service: ApprovalPolicyService = Depends(get_approval_policy_service),
    observability_service: ObservabilityService = Depends(get_observability_service),
) -> DAGScheduler:
    """Return a DAGScheduler for collaboration waves — same collaborators as the main engine."""
    return DAGScheduler(dispatcher, pool, approval_service, approval_policy_service, observability_service)


def get_collaboration_execution_service(
    scheduler: DAGScheduler = Depends(get_collaboration_dag_scheduler),
    checkpoint_store: ExecutionCheckpointStore = Depends(get_execution_checkpoint_store),
    task_registry: ExecutionTaskRegistry = Depends(get_execution_task_registry),
    observability_service: ObservabilityService = Depends(get_observability_service),
    progress_tracker: ProgressTracker = Depends(get_progress_tracker),
    memory_service: MemoryService = Depends(get_memory_service),
) -> ExecutionService:
    """Return the ExecutionService collaboration waves run through — same class, own dispatcher."""
    return ExecutionService(
        scheduler, checkpoint_store, task_registry, observability_service, progress_tracker, memory_service
    )


def get_collaboration_executor(
    coordinator: CollaborationCoordinator = Depends(get_collaboration_coordinator),
    execution_service: ExecutionService = Depends(get_collaboration_execution_service),
) -> CollaborationExecutor:
    """Return a CollaborationExecutor driving waves through the collaboration-scoped ExecutionService."""
    return CollaborationExecutor(coordinator, SubTaskManager(coordinator), execution_service)


def get_collaboration_service(
    coordinator: CollaborationCoordinator = Depends(get_collaboration_coordinator),
    executor: CollaborationExecutor = Depends(get_collaboration_executor),
    capability_registry: AgentCapabilityRegistry = Depends(get_capability_registry),
    message_bus: MessageBus = Depends(get_message_bus),
    observability_service: ObservabilityService = Depends(get_observability_service),
    memory_service: MemoryService = Depends(get_memory_service),
) -> CollaborationService:
    """Provide the CollaborationService — the only object that should be used for collaboration sessions."""
    return CollaborationService(
        coordinator, executor, capability_registry, message_bus, observability_service, memory_service
    )
