"""Tests for the /api/v1/adaptive/* endpoints, against the real app with a
real (MockProvider-backed) Planner-generated plan — mirrors
test_api_v1_reflection.py's own pattern of never hand-building fixtures
for what the real pipeline itself should produce.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.dependencies.memory import get_memory_store
from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_memory() -> Iterator[None]:
    get_memory_store().clear()
    yield
    get_memory_store().clear()


def _ready_plan(session_id: str, step_id: str) -> dict:
    response = client.post(
        "/api/v1/planner/plan",
        json={
            "step": {
                "step_id": step_id,
                "name": "Planner Agent Run",
                "node_name": "planner",
                "inputs": {"user_request": "Please clean my uploaded customer records dataset."},
            },
            "session_id": session_id,
        },
    )
    assert response.status_code == 200, response.text
    plan = dict(response.json()["data"]["planner_output"]["execution_plan"])
    plan["status"] = "ready"
    return plan


def test_explain_returns_a_preview_with_no_stored_optimization_id() -> None:
    plan = _ready_plan("adaptive-sess-1", "adaptive-s1")
    response = client.post("/api/v1/adaptive/explain", json={"plan": plan, "session_id": "adaptive-sess-1"})
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert result["optimization_id"] == ""
    assert result["plan_id"] == plan["plan_id"]


def test_optimize_stores_and_returns_an_optimization_id() -> None:
    plan = _ready_plan("adaptive-sess-2", "adaptive-s2")
    response = client.post("/api/v1/adaptive/optimize", json={"plan": plan, "session_id": "adaptive-sess-2"})
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert result["optimization_id"] != ""


def test_history_and_statistics_and_export() -> None:
    # /planner/plan itself already calls AdaptivePlanningService.optimize() once
    # (Planner Integration) before this test's own explicit call adds a second.
    plan = _ready_plan("adaptive-sess-3", "adaptive-s3")
    optimized = client.post("/api/v1/adaptive/optimize", json={"plan": plan, "session_id": "adaptive-sess-3"}).json()[
        "data"
    ]
    optimization_id = optimized["optimization_id"]

    history_response = client.get("/api/v1/adaptive/history")
    assert history_response.status_code == 200
    assert len(history_response.json()["data"]) == 2

    stats_response = client.get("/api/v1/adaptive/statistics")
    assert stats_response.status_code == 200
    assert stats_response.json()["data"]["total_optimizations"] == 2

    json_export = client.get(f"/api/v1/adaptive/export/json/{optimization_id}")
    assert json_export.status_code == 200
    assert optimization_id in json_export.json()["data"]

    markdown_export = client.get(f"/api/v1/adaptive/export/markdown/{optimization_id}")
    assert markdown_export.status_code == 200
    assert "Plan Optimization" in markdown_export.json()["data"]


def test_export_returns_404_for_unknown_optimization() -> None:
    response = client.get("/api/v1/adaptive/export/json/does-not-exist")
    assert response.status_code == 404
