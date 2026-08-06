"""Tests for the /api/v1/reflection/* endpoints, against the real app with a
real (MockProvider-backed) planner and real File Agent pipeline — mirrors
test_api_v1_collaboration.py's own pattern of never hand-building fixtures
for what the real pipeline itself should produce.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.dependencies.approval import get_approval_policy_service
from backend.dependencies.memory import get_memory_store
from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    get_memory_store().clear()
    yield
    get_memory_store().clear()
    policy_service = get_approval_policy_service()
    policy_service.set_policy(policy_service.get_policy().model_copy(update={"policy_type": "never"}))


def _ready_plan(csv_path: Path, session_id: str, step_id: str) -> dict:
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
    for step in plan["steps"]:
        if step["node_name"] == "file_agent":
            step["inputs"]["dataset_reference"] = str(csv_path)
    return plan


def _csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("region,revenue\nEast,100\nWest,200\n")
    return csv_path


def test_generate_reflection_over_a_real_completed_execution(tmp_path: Path) -> None:
    session_id = "reflect-sess-1"
    plan = _ready_plan(_csv(tmp_path), session_id, "reflect-s1")
    exec_response = client.post("/api/v1/execution/start", json={"plan": plan, "session_id": session_id})
    assert exec_response.status_code == 200, exec_response.text

    response = client.post("/api/v1/reflection/generate", json={"plan": plan})
    assert response.status_code == 200, response.text
    result = response.json()["data"]

    assert result["plan_id"] == plan["plan_id"]
    assert result["review"]["overall_success"] is True
    assert result["review"]["execution_score"]["value"] == 100.0


def test_generate_reflection_raises_404_when_plan_never_ran(tmp_path: Path) -> None:
    plan = _ready_plan(_csv(tmp_path), "reflect-sess-2", "reflect-s2")
    response = client.post("/api/v1/reflection/generate", json={"plan": plan})
    assert response.status_code == 404


def test_get_list_statistics_and_export(tmp_path: Path) -> None:
    session_id = "reflect-sess-3"
    plan = _ready_plan(_csv(tmp_path), session_id, "reflect-s3")
    client.post("/api/v1/execution/start", json={"plan": plan, "session_id": session_id})
    generated = client.post("/api/v1/reflection/generate", json={"plan": plan}).json()["data"]
    reflection_id = generated["reflection_id"]

    get_response = client.get(f"/api/v1/reflection/{reflection_id}")
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["data"]["reflection_id"] == reflection_id

    list_response = client.get("/api/v1/reflection/list")
    assert list_response.status_code == 200
    assert len(list_response.json()["data"]) == 1

    stats_response = client.get("/api/v1/reflection/statistics")
    assert stats_response.status_code == 200
    assert stats_response.json()["data"]["total_reflections"] == 1

    json_export = client.get(f"/api/v1/reflection/export/json/{reflection_id}")
    assert json_export.status_code == 200
    assert reflection_id in json_export.json()["data"]

    markdown_export = client.get(f"/api/v1/reflection/export/markdown/{reflection_id}")
    assert markdown_export.status_code == 200
    assert "Execution Review" in markdown_export.json()["data"]


def test_get_returns_404_for_unknown_reflection() -> None:
    response = client.get("/api/v1/reflection/does-not-exist")
    assert response.status_code == 404
