"""Execution engine providers: dispatcher, pool, scheduler, checkpoint store,
task registry, progress tracker, and the top-level ExecutionService.

Only the genuinely stateful leaves are ``@lru_cache``'d singletons here
(``ExecutionPool``'s semaphore, ``ExecutionCheckpointStore``,
``ExecutionTaskRegistry``) — mirroring exactly how ``AgentExecutionResultStore``
is cached while ``FileAgentService`` itself is not (``backend.dependencies.file_agent``).
``NodeDispatcher``/``DAGScheduler``/``ExecutionService`` hold no state of
their own beyond those injected stores, so they're rebuilt fresh per
request like ``FileAgentService`` is — which matters because the six
underlying ``get_X_agent_service()`` providers are themselves uncached;
``@lru_cache``-ing anything built from their (identity-varying) return
values would silently never hit its cache and defeat the point.
"""

from functools import lru_cache

from fastapi import Depends

from backend.agents.browser.services.browser_agent_service import BrowserAgentService
from backend.agents.executive_summary.services.executive_summary_service import (
    ExecutiveSummaryService,
)
from backend.agents.file.services.file_agent_service import FileAgentService
from backend.agents.planner.services.planner_agent_service import PlannerAgentService
from backend.agents.report.services.report_agent_service import ReportAgentService
from backend.agents.sql.services.sql_agent_service import SQLAgentService
from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.dependencies.approval import (
    get_approval_policy_service,
    get_approval_service,
)
from backend.dependencies.browser_agent import get_browser_agent_service
from backend.dependencies.distributed import get_distributed_execution_service
from backend.dependencies.execution_checkpoint import get_execution_checkpoint_store
from backend.dependencies.executive_summary import get_executive_summary_service
from backend.dependencies.file_agent import get_file_agent_service
from backend.dependencies.memory import get_memory_service
from backend.dependencies.observability import get_observability_service
from backend.dependencies.orchestration import get_planner_agent_service
from backend.dependencies.realtime import get_realtime_service
from backend.dependencies.report_agent import get_report_agent_service
from backend.dependencies.sql_agent import get_sql_agent_service
from backend.distributed.scheduler.dispatch_scheduler import DispatchingAgentService
from backend.distributed.services.distributed_execution_service import (
    DistributedExecutionService,
)
from backend.execution.checkpoint.execution_checkpoint import ExecutionCheckpointStore
from backend.execution.dispatcher.node_dispatcher import NodeDispatcher
from backend.execution.parallel.execution_pool import ExecutionPool
from backend.execution.progress.progress_tracker import ProgressTracker
from backend.execution.scheduler.dag_scheduler import DAGScheduler
from backend.execution.services.execution_service import ExecutionService
from backend.execution.services.task_registry import ExecutionTaskRegistry
from backend.memory.services.memory_service import MemoryService
from backend.observability.services.observability_service import ObservabilityService
from backend.realtime.publishers.execution_publisher import (
    RealtimePublishingAgentService,
)
from backend.realtime.services.realtime_service import RealtimeService


@lru_cache
def get_execution_pool() -> ExecutionPool:
    """Return the process-wide ExecutionPool singleton — bounds concurrent step dispatch."""
    return ExecutionPool()


@lru_cache
def get_execution_task_registry() -> ExecutionTaskRegistry:
    """Return the process-wide ExecutionTaskRegistry singleton."""
    return ExecutionTaskRegistry()


@lru_cache
def get_progress_tracker() -> ProgressTracker:
    """Return a ProgressTracker — stateless, safe to share."""
    return ProgressTracker()


def get_node_dispatcher(
    file_agent_service: FileAgentService = Depends(get_file_agent_service),
    sql_agent_service: SQLAgentService = Depends(get_sql_agent_service),
    browser_agent_service: BrowserAgentService = Depends(get_browser_agent_service),
    report_agent_service: ReportAgentService = Depends(get_report_agent_service),
    executive_summary_service: ExecutiveSummaryService = Depends(get_executive_summary_service),
    planner_agent_service: PlannerAgentService = Depends(get_planner_agent_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
    distributed_execution_service: DistributedExecutionService = Depends(get_distributed_execution_service),
) -> NodeDispatcher:
    """Return the process-wide NodeDispatcher, every existing agent service registered by node_name.

    Registering a future agent needs only one more ``register()`` call
    here — never a change to ``NodeDispatcher`` or ``DAGScheduler``
    themselves. Each of the five real, dispatchable agent services (never
    ``planner`` — Planner never knows workers, see
    ``backend.distributed.services.distributed_execution_service``'s own
    docstring) is wrapped in ``DispatchingAgentService`` (Phase 38, credits
    an eligible registered worker with the step, a no-op with zero workers
    registered) *inside* ``RealtimePublishingAgentService`` (Phase 37) —
    the single choke point every step of the real, parallel ``DAGScheduler``
    dispatches through, giving genuine per-step/per-agent realtime events
    and distributed dispatch bookkeeping with no change to
    ``NodeDispatcher``/``DAGScheduler``/any agent service itself.
    """
    dispatcher = NodeDispatcher()
    dispatcher.register("planner", RealtimePublishingAgentService(planner_agent_service, realtime_service))
    dispatcher.register(
        "file_agent",
        RealtimePublishingAgentService(
            DispatchingAgentService("file_agent", file_agent_service, distributed_execution_service), realtime_service
        ),
    )
    dispatcher.register(
        "sql_agent",
        RealtimePublishingAgentService(
            DispatchingAgentService("sql_agent", sql_agent_service, distributed_execution_service), realtime_service
        ),
    )
    dispatcher.register(
        "browser_agent",
        RealtimePublishingAgentService(
            DispatchingAgentService("browser_agent", browser_agent_service, distributed_execution_service),
            realtime_service,
        ),
    )
    dispatcher.register(
        "report_agent",
        RealtimePublishingAgentService(
            DispatchingAgentService("report_agent", report_agent_service, distributed_execution_service),
            realtime_service,
        ),
    )
    dispatcher.register(
        "executive_summary_agent",
        RealtimePublishingAgentService(
            DispatchingAgentService(
                "executive_summary_agent", executive_summary_service, distributed_execution_service
            ),
            realtime_service,
        ),
    )
    return dispatcher


def get_dag_scheduler(
    dispatcher: NodeDispatcher = Depends(get_node_dispatcher),
    pool: ExecutionPool = Depends(get_execution_pool),
    approval_service: ApprovalService = Depends(get_approval_service),
    approval_policy_service: ApprovalPolicyService = Depends(get_approval_policy_service),
    observability_service: ObservabilityService = Depends(get_observability_service),
) -> DAGScheduler:
    """Return a DAGScheduler wired with the shared, process-wide pool/approval/observability collaborators."""
    return DAGScheduler(dispatcher, pool, approval_service, approval_policy_service, observability_service)


def get_execution_service(
    scheduler: DAGScheduler = Depends(get_dag_scheduler),
    checkpoint_store: ExecutionCheckpointStore = Depends(get_execution_checkpoint_store),
    task_registry: ExecutionTaskRegistry = Depends(get_execution_task_registry),
    observability_service: ObservabilityService = Depends(get_observability_service),
    progress_tracker: ProgressTracker = Depends(get_progress_tracker),
    memory_service: MemoryService = Depends(get_memory_service),
) -> ExecutionService:
    """Provide the ExecutionService — the only object that should be used to run a plan's DAG.

    Every tracked (and possibly paused/running) execution stays
    inspectable/resumable/cancellable across requests via the shared,
    cached ``checkpoint_store``/``task_registry`` — not via caching this
    service object itself. See this module's own docstring for why.
    """
    return ExecutionService(
        scheduler, checkpoint_store, task_registry, observability_service, progress_tracker, memory_service
    )
