"""Tests for backend.federation.models: Cluster behavior."""

import pytest
from pydantic import ValidationError

from backend.federation.models.cluster import Cluster
from backend.federation.models.cluster_capability import ClusterCapability
from backend.federation.models.cluster_status import ClusterStatus


def _cluster(**overrides: object) -> Cluster:
    defaults: dict[str, object] = {
        "cluster_id": "c1", "name": "Cluster One", "endpoint": "https://c1.example.com",
        "capabilities": ClusterCapability(supported_agents=["browser_agent"], maximum_concurrent_executions=2),
    }
    defaults.update(overrides)
    return Cluster(**defaults)  # type: ignore[arg-type]


def test_supports_agent_checks_capabilities() -> None:
    cluster = _cluster()
    assert cluster.supports_agent("browser_agent")
    assert not cluster.supports_agent("sql_agent")


def test_supports_workflow_size() -> None:
    cluster = _cluster(capabilities=ClusterCapability(maximum_workflow_size=5))
    assert cluster.supports_workflow_size(5)
    assert not cluster.supports_workflow_size(6)


def test_has_capacity_respects_maximum() -> None:
    cluster = _cluster(active_remote_executions=["r1"])
    assert cluster.has_capacity()
    full = _cluster(active_remote_executions=["r1", "r2"])
    assert not full.has_capacity()


def test_load_ratio() -> None:
    cluster = _cluster(active_remote_executions=["r1"], capabilities=ClusterCapability(maximum_concurrent_executions=4))
    assert cluster.load_ratio() == 0.25


def test_cluster_is_frozen() -> None:
    cluster = _cluster()
    with pytest.raises(ValidationError):
        cluster.status = ClusterStatus.OFFLINE  # type: ignore[misc]


def test_cluster_defaults_to_online_and_not_local() -> None:
    cluster = _cluster()
    assert cluster.status == ClusterStatus.ONLINE
    assert cluster.is_local is False
    assert cluster.active_remote_executions == []
