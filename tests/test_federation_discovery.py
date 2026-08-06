"""Tests for backend.federation.discovery: ClusterDiscovery and HealthMonitor."""

from datetime import timedelta

from backend.federation.discovery.cluster_discovery import ClusterDiscovery
from backend.federation.discovery.health_monitor import HealthMonitor
from backend.federation.models.cluster_capability import ClusterCapability
from backend.federation.models.cluster_status import ClusterStatus
from backend.federation.registry.cluster_registry import ClusterRegistry


def _capabilities() -> ClusterCapability:
    return ClusterCapability(supported_agents=["browser_agent"], maximum_concurrent_executions=2)


# -- ClusterDiscovery ---------------------------------------------------------------------


def test_register_records_a_registration_event() -> None:
    registry = ClusterRegistry()
    discovery = ClusterDiscovery(registry)
    discovery.register("c1", "Cluster One", "https://c1.example.com", _capabilities())
    history = discovery.history_for("c1")
    assert len(history) == 1
    assert history[0].cluster_id == "c1"


def test_history_is_bounded() -> None:
    registry = ClusterRegistry()
    discovery = ClusterDiscovery(registry)
    for _ in range(25):
        discovery.register("c1", "Cluster One", "https://c1.example.com", _capabilities())
    assert len(discovery.history_for("c1")) == 20


def test_history_for_unknown_cluster_is_empty() -> None:
    discovery = ClusterDiscovery(ClusterRegistry())
    assert discovery.history_for("does-not-exist") == []


# -- HealthMonitor ------------------------------------------------------------------------


def test_sweep_marks_stale_cluster_degraded_then_offline() -> None:
    registry = ClusterRegistry()
    cluster = registry.register("c1", "Cluster One", "https://c1.example.com", _capabilities())
    monitor = HealthMonitor(registry, degraded_after_seconds=60, offline_after_seconds=180)

    monitor.sweep(now=cluster.last_seen + timedelta(seconds=90))
    assert registry.get("c1").status == ClusterStatus.DEGRADED

    monitor.sweep(now=cluster.last_seen + timedelta(seconds=200))
    assert registry.get("c1").status == ClusterStatus.OFFLINE
    assert registry.get("c1").health_score == 0.0


def test_sweep_leaves_fresh_cluster_online() -> None:
    registry = ClusterRegistry()
    cluster = registry.register("c1", "Cluster One", "https://c1.example.com", _capabilities())
    monitor = HealthMonitor(registry, degraded_after_seconds=60, offline_after_seconds=180)

    monitor.sweep(now=cluster.last_seen + timedelta(seconds=5))

    assert registry.get("c1").status == ClusterStatus.ONLINE
    assert registry.get("c1").health_score > 0.9


def test_sweep_never_touches_the_local_cluster() -> None:
    registry = ClusterRegistry()
    cluster = registry.register("local", "local", "local://in-process", _capabilities(), is_local=True)
    monitor = HealthMonitor(registry, degraded_after_seconds=1, offline_after_seconds=2)

    changed = monitor.sweep(now=cluster.last_seen + timedelta(seconds=1000))

    assert changed == []
    assert registry.get("local").status == ClusterStatus.ONLINE


def test_sweep_never_touches_already_offline_or_maintenance_clusters() -> None:
    registry = ClusterRegistry()
    registry.register("c1", "Cluster One", "https://c1.example.com", _capabilities())
    registry.set_status("c1", ClusterStatus.MAINTENANCE)
    monitor = HealthMonitor(registry, degraded_after_seconds=1, offline_after_seconds=2)

    changed = monitor.sweep()

    assert changed == []
    assert registry.get("c1").status == ClusterStatus.MAINTENANCE
