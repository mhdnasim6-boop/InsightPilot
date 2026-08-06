"""Tests for backend.federation.registry: ClusterRegistry and FederationDirectory."""

import pytest

from backend.federation.exceptions import ClusterNotFoundError
from backend.federation.models.cluster_capability import ClusterCapability
from backend.federation.models.cluster_status import ClusterStatus
from backend.federation.registry.cluster_registry import ClusterRegistry
from backend.federation.registry.federation_directory import FederationDirectory


def _capabilities(**overrides: object) -> ClusterCapability:
    defaults: dict[str, object] = {"supported_agents": ["browser_agent"], "maximum_concurrent_executions": 2}
    defaults.update(overrides)
    return ClusterCapability(**defaults)  # type: ignore[arg-type]


# -- ClusterRegistry --------------------------------------------------------------------


def test_register_creates_an_online_cluster() -> None:
    registry = ClusterRegistry()
    cluster = registry.register("c1", "Cluster One", "https://c1.example.com", _capabilities())
    assert cluster.status == ClusterStatus.ONLINE
    assert cluster.registered_at is not None
    assert cluster.last_seen is not None


def test_register_is_idempotent_and_preserves_registered_at() -> None:
    registry = ClusterRegistry()
    first = registry.register("c1", "Cluster One", "https://c1.example.com", _capabilities())
    second = registry.register("c1", "Renamed", "https://c1.example.com", _capabilities(supported_agents=["sql_agent"]))
    assert second.registered_at == first.registered_at
    assert second.name == "Renamed"
    assert second.supports_agent("sql_agent")


def test_get_raises_for_unknown_cluster() -> None:
    registry = ClusterRegistry()
    with pytest.raises(ClusterNotFoundError):
        registry.get("does-not-exist")


def test_touch_refreshes_last_seen_and_revives_offline_cluster() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "Cluster One", "https://c1.example.com", _capabilities())
    registry.set_status("c1", ClusterStatus.OFFLINE, health_score=0.0)
    revived = registry.touch("c1")
    assert revived.status == ClusterStatus.ONLINE
    assert revived.health_score == 1.0


def test_add_and_remove_active_execution() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "Cluster One", "https://c1.example.com", _capabilities())
    credited = registry.add_active_execution("c1", "r1")
    assert credited.active_remote_executions == ["r1"]
    released = registry.remove_active_execution("c1", "r1")
    assert released.active_remote_executions == []


def test_remove_deregisters_a_cluster() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "Cluster One", "https://c1.example.com", _capabilities())
    registry.remove("c1")
    with pytest.raises(ClusterNotFoundError):
        registry.get("c1")


def test_list_by_status() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities())
    registry.register("c2", "Two", "https://c2.example.com", _capabilities())
    registry.set_status("c2", ClusterStatus.OFFLINE)
    assert [c.cluster_id for c in registry.list_by_status(ClusterStatus.ONLINE)] == ["c1"]


# -- FederationDirectory ----------------------------------------------------------------


def test_clusters_supporting_agent() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities(supported_agents=["browser_agent"]))
    registry.register("c2", "Two", "https://c2.example.com", _capabilities(supported_agents=["sql_agent"]))
    directory = FederationDirectory(registry)
    assert [c.cluster_id for c in directory.clusters_supporting_agent("sql_agent")] == ["c2"]


def test_clusters_supporting_plugin_and_mcp_adapter() -> None:
    registry = ClusterRegistry()
    registry.register(
        "c1", "One", "https://c1.example.com",
        _capabilities(supported_plugins=["csv_statistics_plugin"], supported_mcp_adapters=["adapter-1"]),
    )
    directory = FederationDirectory(registry)
    assert [c.cluster_id for c in directory.clusters_supporting_plugin("csv_statistics_plugin")] == ["c1"]
    assert [c.cluster_id for c in directory.clusters_supporting_mcp_adapter("adapter-1")] == ["c1"]


def test_eligible_clusters_filters_by_capability_status_capacity_and_size() -> None:
    registry = ClusterRegistry()
    registry.register("online", "Online", "https://a.example.com", _capabilities(maximum_workflow_size=10))
    registry.register("offline", "Offline", "https://b.example.com", _capabilities())
    registry.set_status("offline", ClusterStatus.OFFLINE)
    registry.register("full", "Full", "https://c.example.com", _capabilities(maximum_concurrent_executions=1))
    registry.add_active_execution("full", "r1")
    registry.register("too_small", "TooSmall", "https://d.example.com", _capabilities(maximum_workflow_size=1))
    directory = FederationDirectory(registry)

    eligible = directory.eligible_clusters(required_agents=["browser_agent"], step_count=5)

    assert [c.cluster_id for c in eligible] == ["online"]


def test_eligible_clusters_includes_degraded() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "One", "https://c1.example.com", _capabilities())
    registry.set_status("c1", ClusterStatus.DEGRADED)
    directory = FederationDirectory(registry)
    assert [c.cluster_id for c in directory.eligible_clusters(["browser_agent"], 1)] == ["c1"]
