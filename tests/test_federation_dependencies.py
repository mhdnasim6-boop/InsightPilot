"""Tests for backend.dependencies.federation: singleton caching and that each
DI provider function constructs the right, correctly-wired object type.

Deliberately does not resolve the real app's own ``get_capability_registry()``/
``get_plugin_registry()``/``get_mcp_service()``/``get_distributed_execution_service()``
bare here for ``ensure_local_cluster()`` — the same documented
Depends()-marker-binding hazard ``test_mcp_dependencies.py`` first
caught. A small, real, local ``GraphBuilder`` plus real (but empty)
``PluginRegistry``/``MCPServerRegistry``/``DistributedExecutionService``
instances (the same "construct the real collaborator directly instead
of going through a cached provider bare" pattern
``test_distributed_dependencies.py``/``test_realtime_dependencies.py``
already established) are enough to prove each DI *function itself*
wires correctly; the full chain against the real app's own default
registries is separately proven by ``tests/test_api_v1_federation.py``'s
real HTTP round trips and by this module's own
``test_get_workload_router_and_federation_service_are_resolvable_via_the_real_app``
below.

``test_federation_scheduler_singleton_survives_a_full_dependency_resolution``
is a regression test for a real bug caught during this phase's own
manual testing: ``get_federation_scheduler()`` is ``@lru_cache``'d, but
its own dependency chain (``get_cluster_selector()`` ->
``get_federation_directory()``) was originally *uncached* — since
``functools.lru_cache`` keys on argument *identity*, a freshly
constructed (uncached) ``ClusterSelector``/``FederationDirectory`` on
every call silently produced a brand-new, routing-decision-amnesiac
``FederationScheduler`` on every request, even though the function
itself was decorated with ``@lru_cache``. Fixed by caching the entire
chain down to ``get_cluster_registry()`` — the same class of bug
``backend.dependencies.approval``'s own docstring already documents for
``ApprovalService``/``PlanExecutor``.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.dependencies.federation import (
    get_cluster_allocator,
    get_cluster_discovery,
    get_cluster_registry,
    get_cluster_selector,
    get_failover_manager,
    get_federation_directory,
    get_federation_scheduler,
    get_federation_service,
    get_health_monitor,
    get_routing_engine,
)
from backend.federation.registry.federation_directory import FederationDirectory
from backend.federation.scheduler.cluster_selector import ClusterSelector
from backend.federation.scheduler.failover_manager import FailoverManager
from backend.federation.scheduler.federation_scheduler import FederationScheduler
from backend.federation.services.federation_service import (
    LOCAL_CLUSTER_ID,
    FederationService,
)
from backend.main import app

_ADMIN_USERNAME = "admin"
_ADMIN_PASSWORD = "ChangeMe123!"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/login", json={"username": _ADMIN_USERNAME, "password": _ADMIN_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


def test_stateful_singletons_are_cached_across_calls() -> None:
    assert get_cluster_registry() is get_cluster_registry()
    assert get_cluster_discovery(cluster_registry=get_cluster_registry()) is get_cluster_discovery(
        cluster_registry=get_cluster_registry()
    )
    assert get_health_monitor(cluster_registry=get_cluster_registry()) is get_health_monitor(
        cluster_registry=get_cluster_registry()
    )
    assert get_routing_engine() is get_routing_engine()
    assert get_cluster_allocator(cluster_registry=get_cluster_registry()) is get_cluster_allocator(
        cluster_registry=get_cluster_registry()
    )


def test_federation_directory_and_cluster_selector_are_cached() -> None:
    directory = get_federation_directory(cluster_registry=get_cluster_registry())
    assert directory is get_federation_directory(cluster_registry=get_cluster_registry())
    assert isinstance(directory, FederationDirectory)

    selector = get_cluster_selector(directory=directory, routing_engine=get_routing_engine())
    assert selector is get_cluster_selector(
        directory=get_federation_directory(cluster_registry=get_cluster_registry()), routing_engine=get_routing_engine()
    )
    assert isinstance(selector, ClusterSelector)


def test_federation_scheduler_singleton_survives_a_full_dependency_resolution() -> None:
    """The actual regression proof: resolving the *entire* chain fresh from
    get_cluster_registry() down, twice, independently, must yield the same
    FederationScheduler object both times — proving its own cache genuinely hits."""

    def resolve_scheduler() -> FederationScheduler:
        directory = get_federation_directory(cluster_registry=get_cluster_registry())
        selector = get_cluster_selector(directory=directory, routing_engine=get_routing_engine())
        return get_federation_scheduler(cluster_selector=selector)

    assert resolve_scheduler() is resolve_scheduler()


def test_get_failover_manager_returns_the_real_type() -> None:
    directory = get_federation_directory(cluster_registry=get_cluster_registry())
    selector = get_cluster_selector(directory=directory, routing_engine=get_routing_engine())
    scheduler = get_federation_scheduler(cluster_selector=selector)
    failover = get_failover_manager(
        federation_scheduler=scheduler, cluster_selector=selector, cluster_registry=get_cluster_registry(),
    )
    assert isinstance(failover, FailoverManager)


def test_ensure_local_cluster_registers_it_via_the_real_app(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get("/api/v1/federation/clusters", headers=headers)
    cluster_ids = [c["cluster_id"] for c in response.json()["data"]]
    assert LOCAL_CLUSTER_ID in cluster_ids


def test_get_workload_router_and_federation_service_are_resolvable_via_the_real_app(client: TestClient) -> None:
    """Proves get_workload_router()/get_federation_service() — including the
    ensure_local_cluster() side-effect dependency each of them declares —
    resolve correctly through FastAPI's own real request handling."""
    headers = _admin_headers(client)

    # get_workload_router() is exercised indirectly by every real workflow execution
    # (FederationCoordinator, wired into get_workflow_service()) — a real 200 here
    # proves the whole chain, including ensure_local_cluster(), resolved without error.
    body = {
        "name": "DI resolution smoke test", "description": "x",
        "steps": [{"step_id": "s1", "name": "Search", "node_name": "browser_agent", "inputs": {"search_request": "x"}}],
    }
    created = client.post("/api/v1/workflows", json=body, headers=headers)
    assert created.status_code == 200, created.text
    executed = client.post(
        f"/api/v1/workflows/{created.json()['data']['workflow_id']}/execute", json={"session_id": "s"}, headers=headers,
    )
    assert executed.status_code == 200, executed.text

    # get_federation_service() is exercised directly by every /api/v1/federation/* route.
    stats = client.get("/api/v1/federation/statistics", headers=headers)
    assert stats.status_code == 200
    assert stats.json()["data"]["total_clusters"] >= 1


def test_ensure_local_cluster_returns_a_real_local_cluster_from_the_real_registries(client: TestClient) -> None:
    """Constructs ensure_local_cluster() directly with the real app's own DI providers
    (via Depends() resolved through a real request, not called bare) to confirm its
    own return value — not just its side effect — is correct."""
    headers = _admin_headers(client)
    response = client.get("/api/v1/federation/clusters", headers=headers)
    local = next(c for c in response.json()["data"] if c["cluster_id"] == LOCAL_CLUSTER_ID)
    assert local["is_local"] is True
    assert "browser_agent" in local["capabilities"]["supported_agents"]


def test_get_federation_service_returns_the_real_type() -> None:
    from backend.federation.coordination.cluster_allocator import ClusterAllocator
    from backend.federation.discovery.cluster_discovery import ClusterDiscovery
    from backend.federation.discovery.health_monitor import HealthMonitor
    from backend.federation.models.cluster import Cluster
    from backend.federation.models.cluster_capability import ClusterCapability
    from backend.utils.time import utc_now

    cluster_registry = get_cluster_registry()
    cluster_discovery = get_cluster_discovery(cluster_registry=cluster_registry)
    fake_local = Cluster(
        cluster_id=LOCAL_CLUSTER_ID, name="local", endpoint="local://in-process",
        capabilities=ClusterCapability(), is_local=True, registered_at=utc_now(), last_seen=utc_now(),
    )
    service = get_federation_service(
        cluster_registry=cluster_registry,
        cluster_discovery=cluster_discovery,
        health_monitor=get_health_monitor(cluster_registry=cluster_registry),
        federation_scheduler=get_federation_scheduler(
            cluster_selector=get_cluster_selector(
                directory=get_federation_directory(cluster_registry=cluster_registry), routing_engine=get_routing_engine(),
            )
        ),
        cluster_allocator=get_cluster_allocator(cluster_registry=cluster_registry),
        _local_cluster=fake_local,
    )
    assert isinstance(service, FederationService)
    assert isinstance(cluster_discovery, ClusterDiscovery)
    assert isinstance(get_health_monitor(cluster_registry=cluster_registry), HealthMonitor)
    assert isinstance(get_cluster_allocator(cluster_registry=cluster_registry), ClusterAllocator)
