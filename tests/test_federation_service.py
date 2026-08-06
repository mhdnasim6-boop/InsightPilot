"""Tests for backend.federation.services.federation_service.FederationService
— the one public entry point: cluster lifecycle, health, statistics, routing.
"""

import pytest

from backend.federation.coordination.cluster_allocator import ClusterAllocator
from backend.federation.discovery.cluster_discovery import ClusterDiscovery
from backend.federation.discovery.health_monitor import HealthMonitor
from backend.federation.exceptions import (
    CannotRemoveLocalClusterError,
    ClusterNotFoundError,
)
from backend.federation.models.cluster_capability import ClusterCapability
from backend.federation.registry.cluster_registry import ClusterRegistry
from backend.federation.registry.federation_directory import FederationDirectory
from backend.federation.scheduler.cluster_selector import ClusterSelector
from backend.federation.scheduler.federation_scheduler import FederationScheduler
from backend.federation.scheduler.routing_engine import RoutingEngine
from backend.federation.services.federation_service import (
    LOCAL_CLUSTER_ID,
    FederationService,
)


def _capabilities() -> ClusterCapability:
    return ClusterCapability(supported_agents=["browser_agent"], maximum_concurrent_executions=2)


def _build_service() -> FederationService:
    cluster_registry = ClusterRegistry()
    cluster_discovery = ClusterDiscovery(cluster_registry)
    health_monitor = HealthMonitor(cluster_registry)
    selector = ClusterSelector(FederationDirectory(cluster_registry), RoutingEngine())
    federation_scheduler = FederationScheduler(selector)
    cluster_allocator = ClusterAllocator(cluster_registry)
    service = FederationService(cluster_registry, cluster_discovery, health_monitor, federation_scheduler, cluster_allocator)
    cluster_discovery.register(LOCAL_CLUSTER_ID, "local", "local://in-process", ClusterCapability(), is_local=True)
    return service


def test_register_cluster_returns_online_cluster() -> None:
    service = _build_service()
    cluster = service.register_cluster("c1", "Cluster One", "https://c1.example.com", _capabilities())
    assert cluster.status.value == "online"


def test_remove_cluster_raises_for_local_cluster() -> None:
    service = _build_service()
    with pytest.raises(CannotRemoveLocalClusterError):
        service.remove_cluster(LOCAL_CLUSTER_ID)


def test_remove_cluster_raises_for_unknown_cluster() -> None:
    service = _build_service()
    with pytest.raises(ClusterNotFoundError):
        service.remove_cluster("does-not-exist")


def test_remove_cluster_removes_a_real_remote_cluster() -> None:
    service = _build_service()
    service.register_cluster("c1", "Cluster One", "https://c1.example.com", _capabilities())
    service.remove_cluster("c1")
    with pytest.raises(ClusterNotFoundError):
        service.get_cluster("c1")


def test_list_clusters_always_includes_the_local_cluster() -> None:
    service = _build_service()
    assert LOCAL_CLUSTER_ID in [c.cluster_id for c in service.list_clusters()]


def test_get_health_returns_every_cluster() -> None:
    service = _build_service()
    service.register_cluster("c1", "Cluster One", "https://c1.example.com", _capabilities())
    assert len(service.get_health()) == 2


def test_federation_statistics_aggregates_across_clusters() -> None:
    service = _build_service()
    service.register_cluster("c1", "Cluster One", "https://c1.example.com", _capabilities())
    stats = service.federation_statistics()
    assert stats.total_clusters == 2
    assert stats.online_clusters == 2


def test_list_routing_decisions_starts_empty() -> None:
    service = _build_service()
    assert service.list_routing_decisions() == []


def test_export_json_and_mermaid_do_not_raise() -> None:
    service = _build_service()
    service.register_cluster("c1", "Cluster One", "https://c1.example.com", _capabilities())
    assert "c1" in service.export_json()
    assert "flowchart" in service.export_mermaid()
