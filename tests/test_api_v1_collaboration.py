"""Tests for the /api/v1/collaboration/* endpoints, against the real app with
real agent services (real IngestionService/CleaningService/AnalysisService/
ReportService via a real temp CSV pipeline) — mirrors test_api_v1_execution.py's
own pattern of never hand-building fixtures for what the real pipeline itself
should produce.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.dependencies.approval import get_approval_policy_service
from backend.dependencies.collaboration import get_collaboration_store
from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    get_collaboration_store().clear()
    yield
    get_collaboration_store().clear()
    policy_service = get_approval_policy_service()
    policy_service.set_policy(policy_service.get_policy().model_copy(update={"policy_type": "never"}))


def _start(csv_path: Path, session_id: str = "collab-sess-1", generate_report: bool = False) -> dict:
    response = client.post(
        "/api/v1/collaboration/start",
        json={
            "goal": "Analyze sales.csv",
            "session_id": session_id,
            "assigned_agent": "file_agent",
            "description": "Ingest and analyze",
            "inputs": {"dataset_reference": str(csv_path), "generate_report": generate_report},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("a,b\n1,2\n3,4\n5,6\n")
    return csv_path


def test_list_capabilities_excludes_planner_and_approval_nodes() -> None:
    response = client.get("/api/v1/collaboration/capabilities")
    assert response.status_code == 200, response.text
    names = {c["name"] for c in response.json()["data"]}
    assert names == {"file_agent", "sql_agent", "browser_agent", "report_agent", "executive_summary_agent"}


def test_start_creates_a_draft_session_with_one_pending_subtask(tmp_path: Path) -> None:
    task = _start(_csv(tmp_path))
    assert task["status"] == "draft"
    assert len(task["subtasks"]) == 1
    subtask = next(iter(task["subtasks"].values()))
    assert subtask["status"] == "pending"
    assert subtask["assigned_agent"] == "file_agent"


def test_delegate_adds_a_second_subtask(tmp_path: Path) -> None:
    task = _start(_csv(tmp_path))
    file_subtask_id = task["subtask_order"][0]

    response = client.post(
        f"/api/v1/collaboration/{task['collaboration_id']}/delegate",
        json={
            "assigned_agent": "report_agent",
            "description": "Build report",
            "inputs": {"report_config": {}},
            "dependencies": [file_subtask_id],
        },
    )

    assert response.status_code == 200, response.text
    subtask = response.json()["data"]
    assert subtask["assigned_agent"] == "report_agent"
    assert subtask["dependencies"] == [file_subtask_id]


def test_run_executes_file_agent_and_routes_artifacts_to_report_agent(tmp_path: Path) -> None:
    task = _start(_csv(tmp_path))
    file_subtask_id = task["subtask_order"][0]
    collaboration_id = task["collaboration_id"]

    delegated = client.post(
        f"/api/v1/collaboration/{collaboration_id}/delegate",
        json={
            "assigned_agent": "report_agent",
            "description": "Build report",
            "inputs": {"report_config": {}},
            "dependencies": [file_subtask_id],
        },
    ).json()["data"]

    run_response = client.post(f"/api/v1/collaboration/{collaboration_id}/run")
    assert run_response.status_code == 200, run_response.text
    task = run_response.json()["data"]

    assert task["status"] == "completed"
    report_result = task["subtasks"][delegated["subtask_id"]]["result"]
    assert report_result["report_document"] is not None

    history = client.get(f"/api/v1/collaboration/{collaboration_id}/history").json()["data"]
    assert len(history["artifact_exchanges"]) == 1
    assert "dataset" in history["artifact_exchanges"][0]["artifact_keys"]


def test_run_pauses_for_approval_and_resume_completes(tmp_path: Path) -> None:
    client.put("/api/v1/approvals/policy", json={"policy_type": "always"})
    task = _start(_csv(tmp_path))
    collaboration_id = task["collaboration_id"]

    paused = client.post(f"/api/v1/collaboration/{collaboration_id}/run").json()["data"]
    assert paused["status"] == "paused"

    pending = client.get("/api/v1/approvals/pending").json()["data"]
    approval_id = next(a["approval_id"] for a in pending)
    approve = client.post(f"/api/v1/approvals/{approval_id}/approve", json={"approver": "qa"})
    assert approve.status_code == 200

    resumed = client.post(f"/api/v1/collaboration/{collaboration_id}/resume")
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["data"]["status"] == "completed"


def test_cancel_marks_session_cancelled(tmp_path: Path) -> None:
    task = _start(_csv(tmp_path))
    response = client.post(f"/api/v1/collaboration/{task['collaboration_id']}/cancel")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "cancelled"


def test_get_returns_404_for_unknown_collaboration() -> None:
    response = client.get("/api/v1/collaboration/does-not-exist")
    assert response.status_code == 404


def test_get_collaboration_returns_current_state(tmp_path: Path) -> None:
    task = _start(_csv(tmp_path))
    response = client.get(f"/api/v1/collaboration/{task['collaboration_id']}")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["collaboration_id"] == task["collaboration_id"]


def test_statistics_reflects_started_sessions(tmp_path: Path) -> None:
    _start(_csv(tmp_path))
    response = client.get("/api/v1/collaboration/statistics")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["total_sessions"] == 1
