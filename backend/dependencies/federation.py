"""Federation providers: registry, directory, discovery, health, scheduler,
failover, coordination, and the top-level FederationService.

Caching mirrors this package's own established convention (Phase 38's
own ``backend.dependencies.distributed`` docstring): the genuinely
stateful collaborators (``ClusterRegistry``, ``FederationScheduler``,
``ClusterAllocator``) are ``@lru_cache``'d process-wide singletons — a
cluster registered in one request must still be there in the next.
Every stateless composition on top is left uncached, mirroring
``get_distributed_execution_service``/``get_workflow_service``: cheap to
rebuild, and every piece of state that must survive across requests
already lives in the cached collaborators these functions are handed.
"""

from functools import lru_cache

from fastapi import Depends

from backend.collaboration.coordinator.capability_registry import (
    AgentCapabilityRegistry,
)
from backend.dependencies.distributed import get_distributed_execution_service
from backend.dependencies.mcp import get_mcp_service
from backend.dependencies.orchestration import get_capability_registry
from backend.dependencies.plugins import get_plugin_registry
from backend.distributed.services.distributed_execution_service import (
    DistributedExecutionService,
)
from backend.federation.coordination.cluster_allocator import ClusterAllocator
from backend.federation.coordination.workload_router import WorkloadRouter
from backend.federation.discovery.cluster_discovery import ClusterDiscovery
from backend.federation.discovery.health_monitor import HealthMonitor
from backend.federation.models.cluster import Cluster
from backend.federation.models.cluster_capability import ClusterCapability
from backend.federation.registry.cluster_registry import ClusterRegistry
from backend.federation.registry.federation_directory import FederationDirectory
from backend.federation.scheduler.cluster_selector import ClusterSelector
from backend.federation.scheduler.failover_manager import FailoverManager
from backend.federation.scheduler.federation_scheduler import FederationScheduler
from backend.federation.scheduler.routing_engine import RoutingEngine
from backend.federation.services.federation_service import (
    LOCAL_CLUSTER_ENDPOINT,
    LOCAL_CLUSTER_ID,
    FederationService,
)
from backend.mcp.services.mcp_service import MCPService
from backend.plugins.lifecycle.lifecycle import PluginState
from backend.plugins.registry.plugin_registry import PluginRegistry
from config.settings import Settings, get_settings

_LOCAL_CLUSTER_WORKFLOW_FEATURES = [
    "approval_gating", "adaptive_planning", "reflection", "collaboration", "plugins", "mcp", "realtime", "distributed",
]


@lru_cache
def get_cluster_registry() -> ClusterRegistry:
    """Return the process-wide ClusterRegistry singleton — every registered cluster lives here."""
    return ClusterRegistry()


@lru_cache
def get_cluster_discovery(cluster_registry: ClusterRegistry = Depends(get_cluster_registry)) -> ClusterDiscovery:
    """Return the process-wide ClusterDiscovery singleton — keeps each cluster's registration history."""
    return ClusterDiscovery(cluster_registry)


def ensure_local_cluster(
    cluster_discovery: ClusterDiscovery = Depends(get_cluster_discovery),
    agent_capability_registry: AgentCapabilityRegistry = Depends(get_capability_registry),
    plugin_registry: PluginRegistry = Depends(get_plugin_registry),
    mcp_service: MCPService = Depends(get_mcp_service),
    distributed_execution_service: DistributedExecutionService = Depends(get_distributed_execution_service),
    settings: Settings = Depends(get_settings),
) -> Cluster:
    """Idempotently (re-)register this process's own local cluster from the real, live
    registries it already has, and return it fresh.

    A real dependency of every provider below that touches cluster state
    (``get_federation_directory()``, ``get_federation_service()``) — not
    just ``get_federation_service()`` alone — so the local cluster is
    guaranteed to exist and be current on *every* path that might route
    or query it, including the ``FederationCoordinator``/``WorkloadRouter``
    path that never constructs a ``FederationService`` at all. FastAPI
    de-duplicates a dependency within one request, so this only actually
    runs once per request no matter how many providers depend on it.
    """
    supported_agents = [capability.name for capability in agent_capability_registry.discover()]
    supported_plugins = [record.manifest.id for record in plugin_registry.list() if record.state == PluginState.REGISTERED]
    supported_mcp_adapters = [server.server_id for server in mcp_service.list_servers()]
    total_capacity = distributed_execution_service.cluster_statistics().total_capacity
    capabilities = ClusterCapability(
        supported_agents=supported_agents, supported_plugins=supported_plugins,
        supported_mcp_adapters=supported_mcp_adapters, maximum_concurrent_executions=max(1, total_capacity),
        supported_workflow_features=_LOCAL_CLUSTER_WORKFLOW_FEATURES,
    )
    return cluster_discovery.register(
        cluster_id=LOCAL_CLUSTER_ID, name="local", endpoint=LOCAL_CLUSTER_ENDPOINT,
        capabilities=capabilities, version=settings.app_version,
        registered_workers=len(distributed_execution_service.list_workers()),
        metadata={"environment": settings.environment}, is_local=True,
    )


@lru_cache
def get_federation_directory(cluster_registry: ClusterRegistry = Depends(get_cluster_registry)) -> FederationDirectory:
    """Return the process-wide FederationDirectory singleton.

    Cached deliberately — not just for its own stateless-wrapper
    efficiency, but because ``get_cluster_selector()``/``get_federation_scheduler()``
    are themselves cached and take this (transitively) as an argument:
    ``functools.lru_cache`` keys on argument *identity*, so an uncached
    ``FederationDirectory`` here would silently defeat
    ``FederationScheduler``'s own cross-request caching, producing a
    fresh (and therefore routing-decision-amnesiac) scheduler on every
    request — verified empirically before fixing, the same class of bug
    ``backend.dependencies.approval``'s own docstring documents for
    ``ApprovalService``/``PlanExecutor``. This reads the shared
    ``cluster_registry`` fresh on every *call* (``eligible_clusters()``
    etc. all read live, never cache their own results), so caching the
    thin wrapper object itself loses no freshness.
    """
    return FederationDirectory(cluster_registry)


@lru_cache
def get_health_monitor(cluster_registry: ClusterRegistry = Depends(get_cluster_registry)) -> HealthMonitor:
    """Return the process-wide HealthMonitor singleton."""
    return HealthMonitor(cluster_registry)


@lru_cache
def get_routing_engine() -> RoutingEngine:
    """Return the process-wide RoutingEngine singleton. Stateless — cached only for identity reuse."""
    return RoutingEngine()


@lru_cache
def get_cluster_selector(
    directory: FederationDirectory = Depends(get_federation_directory),
    routing_engine: RoutingEngine = Depends(get_routing_engine),
) -> ClusterSelector:
    """Return the process-wide ClusterSelector singleton. Cached for the same
    argument-identity-stability reason ``get_federation_directory()`` documents."""
    return ClusterSelector(directory, routing_engine)


@lru_cache
def get_federation_scheduler(cluster_selector: ClusterSelector = Depends(get_cluster_selector)) -> FederationScheduler:
    """Return the process-wide FederationScheduler singleton — every routing decision lives here."""
    return FederationScheduler(cluster_selector)


def get_failover_manager(
    federation_scheduler: FederationScheduler = Depends(get_federation_scheduler),
    cluster_selector: ClusterSelector = Depends(get_cluster_selector),
    cluster_registry: ClusterRegistry = Depends(get_cluster_registry),
) -> FailoverManager:
    """Provide a FailoverManager wired to the shared, process-wide collaborators."""
    return FailoverManager(federation_scheduler, cluster_selector, cluster_registry)


@lru_cache
def get_cluster_allocator(cluster_registry: ClusterRegistry = Depends(get_cluster_registry)) -> ClusterAllocator:
    """Return the process-wide ClusterAllocator singleton — every RemoteExecution lives here."""
    return ClusterAllocator(cluster_registry)


def get_workload_router(
    federation_scheduler: FederationScheduler = Depends(get_federation_scheduler),
    failover_manager: FailoverManager = Depends(get_failover_manager),
    cluster_allocator: ClusterAllocator = Depends(get_cluster_allocator),
    _local_cluster: Cluster = Depends(ensure_local_cluster),
) -> WorkloadRouter:
    """Provide a WorkloadRouter wired to the shared, process-wide collaborators — used by
    ``FederationCoordinator`` (``backend.dependencies.workflows``) to route each real
    ``WorkflowService.execute()`` call to a credited cluster before delegating.

    Depends on ``ensure_local_cluster`` purely for its side effect — the
    local cluster must exist and be current *before* ``FederationCoordinator``
    ever calls ``route()`` — the parameter itself is unused here.
    """
    return WorkloadRouter(federation_scheduler, failover_manager, cluster_allocator)


def get_federation_service(
    cluster_registry: ClusterRegistry = Depends(get_cluster_registry),
    cluster_discovery: ClusterDiscovery = Depends(get_cluster_discovery),
    health_monitor: HealthMonitor = Depends(get_health_monitor),
    federation_scheduler: FederationScheduler = Depends(get_federation_scheduler),
    cluster_allocator: ClusterAllocator = Depends(get_cluster_allocator),
    _local_cluster: Cluster = Depends(ensure_local_cluster),
) -> FederationService:
    """Provide the FederationService — the only object anything should use for cluster
    registration, health, routing, and failover.

    Deliberately uncached, mirroring ``get_distributed_execution_service``/
    ``get_workflow_service``: every piece of state that must survive
    across requests already lives in the cached ``ClusterRegistry``/
    ``FederationScheduler``/``ClusterAllocator`` this function's own
    dependencies are built from. Depends on ``ensure_local_cluster``
    directly (see that function's own docstring) rather than deriving
    local capabilities itself, so there is exactly one place that logic
    lives — shared with the ``FederationCoordinator``/``WorkloadRouter``
    path via ``get_federation_directory()``'s own identical dependency.
    """
    return FederationService(
        cluster_registry=cluster_registry, cluster_discovery=cluster_discovery, health_monitor=health_monitor,
        federation_scheduler=federation_scheduler, cluster_allocator=cluster_allocator,
    )
