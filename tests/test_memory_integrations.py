"""Tests proving every integration point automatically writes to MemoryService
through the real app — no test here calls MemoryStore/MemoryService directly;
they all exercise the exact same REST paths a real user/agent would.

``MemoryStore`` is a process-wide DI singleton shared by the whole test
suite via ``TestClient(app)`` — the ``_clear_memory`` fixture empties it
before every test here, mirroring ``test_api_v1_memory.py``'s own pattern.
"""

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.dependencies.approval import get_approval_policy_service
from backend.dependencies.memory import get_memory_store
from backend.main import app

client = TestClient(app)

CSV_BYTES = (
    b"date,region,revenue\n"
    b"2024-01-01,East,100\n"
    b"2024-02-01,East,150\n"
    b"2024-01-01,West,50\n"
    b"2024-02-01,West,9000\n"
)


@pytest.fixture(autouse=True)
def _clear_memory() -> Iterator[None]:
    get_memory_store().clear()
    yield
    get_memory_store().clear()
    get_approval_policy_service().set_policy(
        get_approval_policy_service().get_policy().model_copy(update={"policy_type": "never"})
    )


def _memories_by_type(memory_type: str) -> list[dict]:
    return [m for m in client.get("/api/v1/memory").json()["data"] if m["memory_type"] == memory_type]


def _generate_plan(user_request: str, step_id: str, session_id: str) -> dict:
    response = client.post(
        "/api/v1/planner/plan",
        json={
            "step": {
                "step_id": step_id,
                "name": "Planner Agent Run",
                "node_name": "planner",
                "inputs": {"user_request": user_request},
            },
            "session_id": session_id,
        },
    )
    assert response.status_code == 200, response.text
    plan = dict(response.json()["data"]["planner_output"]["execution_plan"])
    plan["status"] = "ready"
    return plan


def test_planner_service_remembers_a_decision_after_planning() -> None:
    _generate_plan("Please clean my uploaded customer records dataset.", "mem-int-s1", "mem-int-sess-1")

    decisions = _memories_by_type("decision")

    assert len(decisions) == 1
    assert decisions[0]["metadata"]["session_id"] == "mem-int-sess-1"
    assert "plan" in decisions[0]["tags"]


def test_execution_service_remembers_an_execution_memory_when_terminal() -> None:
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "mem-int-s2", "mem-int-sess-2")

    response = client.post("/api/v1/execution/start", json={"plan": plan, "session_id": "mem-int-sess-2"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] in {"completed", "failed"}

    executions = _memories_by_type("execution")
    assert len(executions) == 1
    assert executions[0]["content"]["plan_id"] == plan["plan_id"]


def test_approval_service_remembers_an_approval_decision() -> None:
    client.put("/api/v1/approvals/policy", json={"policy_type": "always"})
    plan = _generate_plan("Please clean my uploaded customer records dataset.", "mem-int-s3", "mem-int-sess-3")

    executed = client.post("/api/v1/execution/start", json={"plan": plan, "session_id": "mem-int-sess-3"}).json()[
        "data"
    ]
    assert executed["status"] == "paused"

    pending = client.get("/api/v1/approvals/pending").json()["data"]
    approval_id = next(a["approval_id"] for a in pending if a["plan_id"] == plan["plan_id"])
    approve_response = client.post(f"/api/v1/approvals/{approval_id}/approve", json={"approver": "qa"})
    assert approve_response.status_code == 200

    approvals = _memories_by_type("approval")
    assert len(approvals) == 1
    assert approvals[0]["content"]["approver"] == "qa"
    assert approvals[0]["content"]["decision"] == "approved"


def test_file_agent_remembers_dataset_analysis_visualization_and_report(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text("a,b\n1,2\n3,4\n5,6\n")

    response = client.post(
        "/api/v1/agents/file/execute",
        json={
            "step": {
                "step_id": "mem-int-file-1",
                "name": "File run",
                "node_name": "file_agent",
                "inputs": {"dataset_reference": str(csv_file), "generate_report": True},
            },
            "session_id": "mem-int-file-sess",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "completed"

    assert len(_memories_by_type("dataset")) == 1
    assert len(_memories_by_type("analysis")) == 1
    assert len(_memories_by_type("visualization")) == 1
    assert len(_memories_by_type("report")) == 1


def test_browser_agent_remembers_external_knowledge() -> None:
    session_id = client.post("/api/v1/sessions").json()["data"]["session_id"]

    response = client.post(
        "/api/v1/agents/browser/execute",
        json={
            "step": {
                "step_id": "mem-int-browser-1",
                "name": "Browser run",
                "node_name": "browser_agent",
                "inputs": {"search_request": "market trends 2026"},
            },
            "session_id": session_id,
        },
    )
    assert response.status_code == 200, response.text

    external_knowledge = _memories_by_type("external_knowledge")
    assert len(external_knowledge) >= 1
    assert external_knowledge[0]["content"]["query"] == "market trends 2026"


def test_chat_service_remembers_a_conversation_turn() -> None:
    session_id = client.post("/api/v1/sessions").json()["data"]["session_id"]
    upload = client.post(
        "/api/v1/datasets/upload",
        data={"session_id": session_id},
        files={"file": ("sales.csv", io.BytesIO(CSV_BYTES), "text/csv")},
    ).json()["data"]
    outcome = client.post(f"/api/v1/datasets/{upload['dataset_id']}/clean").json()["data"]
    analysis = client.post("/api/v1/analysis", json=outcome).json()["data"]
    context = {
        "session_id": session_id,
        "selected_dataset": outcome["dataset"],
        "cleaning_outcome": outcome,
        "analysis_result": analysis,
    }

    response = client.post("/api/v1/chat", json={"question": "What are the KPIs?", "context": context})
    assert response.status_code == 200, response.text

    conversations = _memories_by_type("conversation")
    assert len(conversations) == 1
    assert conversations[0]["metadata"]["session_id"] == session_id
    assert conversations[0]["content"]["question"] == "What are the KPIs?"
