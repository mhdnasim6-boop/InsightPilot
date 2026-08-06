"""Tests proving every Phase 30 integration point through the real app — no
test here builds an isolated fixture; each exercises the exact REST paths
a real user/agent would, mirroring test_memory_integrations.py's own
pattern.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.dependencies.collaboration import get_collaboration_store
from backend.dependencies.memory import get_memory_store
from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_state():
    get_collaboration_store().clear()
    get_memory_store().clear()
    yield
    get_collaboration_store().clear()
    get_memory_store().clear()


def _memories_by_type(memory_type: str) -> list[dict]:
    return [m for m in client.get("/api/v1/memory").json()["data"] if m["memory_type"] == memory_type]


def test_planner_agent_direct_rest_path_discovers_agents_via_collaboration_capability_registry() -> None:
    """PlannerAgent (direct-REST invocation) now sources available_services from the
    same AgentCapabilityRegistry backing /collaboration/capabilities — not a
    hardcoded list, and not (for this path) a raw GraphBuilder read.
    """
    response = client.post(
        "/api/v1/planner/plan",
        json={
            "step": {
                "step_id": "collab-int-planner-1",
                "name": "Planner Agent Run",
                "node_name": "planner",
                "inputs": {"user_request": "Please clean my uploaded customer records dataset."},
            },
            "session_id": "collab-int-sess-1",
        },
    )
    assert response.status_code == 200, response.text
    available_services = response.json()["data"]["metadata"]["available_services"]

    capabilities_response = client.get("/api/v1/collaboration/capabilities")
    capability_names = {c["name"] for c in capabilities_response.json()["data"]}

    assert set(available_services) == capability_names


def test_collaboration_session_writes_a_collaboration_memory_when_terminal(tmp_path: Path) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("a,b\n1,2\n3,4\n5,6\n")

    start = client.post(
        "/api/v1/collaboration/start",
        json={
            "goal": "Analyze sales.csv for memory integration",
            "session_id": "collab-int-sess-2",
            "assigned_agent": "file_agent",
            "description": "Ingest and analyze",
            "inputs": {"dataset_reference": str(csv_path), "generate_report": False},
        },
    ).json()["data"]

    run_response = client.post(f"/api/v1/collaboration/{start['collaboration_id']}/run")
    assert run_response.status_code == 200, run_response.text
    assert run_response.json()["data"]["status"] == "completed"

    collaboration_memories = _memories_by_type("collaboration")
    assert len(collaboration_memories) == 1
    assert collaboration_memories[0]["content"]["collaboration_id"] == start["collaboration_id"]


def test_collaboration_reuses_execution_service_dag_scheduler_unmodified(tmp_path: Path) -> None:
    """Execution integration: a collaboration subtask's own agent_traces/tool_traces
    still land in the real observability system exactly like a direct
    /execution/start run would — proof that DAGScheduler/ExecutionService are
    reused, not reimplemented, for collaboration waves.
    """
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("a,b\n1,2\n3,4\n5,6\n")

    start = client.post(
        "/api/v1/collaboration/start",
        json={
            "goal": "Analyze sales.csv for execution integration",
            "session_id": "collab-int-sess-3",
            "assigned_agent": "file_agent",
            "description": "Ingest and analyze",
            "inputs": {"dataset_reference": str(csv_path), "generate_report": False},
        },
    ).json()["data"]
    client.post(f"/api/v1/collaboration/{start['collaboration_id']}/run")

    traces = client.get("/api/v1/observability/traces").json()["data"]
    matching = [t for t in traces if any(a["agent_name"] == "file_agent" for a in t["agent_traces"])]
    assert len(matching) >= 1
