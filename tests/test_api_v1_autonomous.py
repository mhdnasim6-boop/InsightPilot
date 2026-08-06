"""Tests for the /api/v1/autonomous/* endpoints against the real app — mirrors every
other REST test file's own "exercise the real thing" pattern.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

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


def test_autonomous_endpoints_require_authentication(client: TestClient) -> None:
    assert client.post("/api/v1/autonomous/analyze").status_code == 401
    assert client.get("/api/v1/autonomous/reports").status_code == 401
    assert client.get("/api/v1/autonomous/reports/x").status_code == 401
    assert client.get("/api/v1/autonomous/statistics").status_code == 401
    assert client.get("/api/v1/autonomous/recommendations").status_code == 401


def test_analyze_returns_a_well_formed_report_with_one_decision_per_analyzer(client: TestClient) -> None:
    """The genuinely zero-data path (empty bottlenecks/actions/recommendations, every
    decision HEALTHY) is proven at the analyzer level by
    ``tests/test_autonomous_analyzers.py``'s own ``*_healthy_with_zero_data`` tests —
    process-wide singletons here (ObservabilityService, WorkflowStore, ...) are shared
    with every other test in the suite, so this REST-level test only asserts the
    structural invariants that hold regardless of what other tests have already run.
    """
    headers = _admin_headers(client)
    response = client.post("/api/v1/autonomous/analyze", headers=headers)
    assert response.status_code == 200, response.text
    report = response.json()["data"]
    assert len(report["decisions"]) == 6
    assert {d["analyzer_name"] for d in report["decisions"]} == {
        "ExecutionAnalyzer", "WorkflowAnalyzer", "FederationAnalyzer",
        "DistributedAnalyzer", "ObservabilityAnalyzer", "ResourceAnalyzer",
    }
    assert all(d["verdict"] in {"healthy", "warning", "critical"} for d in report["decisions"])
    assert report["summary"]


def test_every_recommendation_in_a_generated_report_is_advisory_only(client: TestClient) -> None:
    headers = _admin_headers(client)
    report = client.post("/api/v1/autonomous/analyze", headers=headers).json()["data"]
    for recommendation in report["recommendations"]:
        assert recommendation["requires_human_approval"] is True
    for action in report["actions"]:
        assert action["safe_to_automate"] is False


def test_list_reports_includes_every_generated_report(client: TestClient) -> None:
    headers = _admin_headers(client)
    first = client.post("/api/v1/autonomous/analyze", headers=headers).json()["data"]["report_id"]
    second = client.post("/api/v1/autonomous/analyze", headers=headers).json()["data"]["report_id"]

    listed = client.get("/api/v1/autonomous/reports", headers=headers)
    assert listed.status_code == 200
    ids = [r["report_id"] for r in listed.json()["data"]]
    assert first in ids
    assert second in ids


def test_get_report_returns_the_matching_report(client: TestClient) -> None:
    headers = _admin_headers(client)
    generated = client.post("/api/v1/autonomous/analyze", headers=headers).json()["data"]
    fetched = client.get(f"/api/v1/autonomous/reports/{generated['report_id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["data"]["report_id"] == generated["report_id"]


def test_get_report_returns_404_for_an_unknown_id(client: TestClient) -> None:
    headers = _admin_headers(client)
    response = client.get("/api/v1/autonomous/reports/does-not-exist", headers=headers)
    assert response.status_code == 404
    assert response.json()["errors"]["type"] == "OptimizationReportNotFoundError"


def test_statistics_reflects_generated_reports(client: TestClient) -> None:
    headers = _admin_headers(client)
    before = client.get("/api/v1/autonomous/statistics", headers=headers).json()["data"]["total_reports"]
    client.post("/api/v1/autonomous/analyze", headers=headers)
    after = client.get("/api/v1/autonomous/statistics", headers=headers).json()["data"]["total_reports"]
    assert after == before + 1


def test_list_recommendations_returns_a_list(client: TestClient) -> None:
    headers = _admin_headers(client)
    client.post("/api/v1/autonomous/analyze", headers=headers)
    response = client.get("/api/v1/autonomous/recommendations", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)
