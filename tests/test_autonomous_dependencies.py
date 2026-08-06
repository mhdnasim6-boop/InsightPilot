"""Tests for backend.dependencies.autonomous: singleton caching for the one
genuinely stateful collaborator (``OptimizationReportStore``), correct types for
the stateless leaf providers, and that the full ``get_autonomous_service()``
dependency chain resolves cleanly through the real app's own DI wiring.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.autonomous.healing.self_healing_engine import SelfHealingEngine
from backend.autonomous.optimizer.bottleneck_detector import BottleneckDetector
from backend.autonomous.services.autonomous_service import OptimizationReportStore
from backend.dependencies.autonomous import (
    get_bottleneck_detector,
    get_optimization_report_store,
    get_self_healing_engine,
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


def test_optimization_report_store_is_a_cached_process_wide_singleton() -> None:
    assert get_optimization_report_store() is get_optimization_report_store()
    assert isinstance(get_optimization_report_store(), OptimizationReportStore)


def test_get_bottleneck_detector_returns_the_real_type() -> None:
    assert isinstance(get_bottleneck_detector(), BottleneckDetector)


def test_get_self_healing_engine_returns_the_real_type() -> None:
    assert isinstance(get_self_healing_engine(), SelfHealingEngine)


def test_get_autonomous_service_resolves_via_the_real_app_and_reports_persist(client: TestClient) -> None:
    """Proves the full dependency chain — reused WorkflowService/AdaptivePlanningService/
    ObservabilityService/MetricsService/ReflectionService/MemoryService/
    DistributedExecutionService/FederationService/AuditService, plus the cached
    OptimizationReportStore — resolves without error, and that the store's own
    cross-request persistence works through two independent real requests."""
    headers = _admin_headers(client)
    first = client.post("/api/v1/autonomous/analyze", headers=headers)
    assert first.status_code == 200, first.text
    report_id = first.json()["data"]["report_id"]

    listed = client.get("/api/v1/autonomous/reports", headers=headers)
    assert listed.status_code == 200
    assert any(r["report_id"] == report_id for r in listed.json()["data"])
