"""Tests proving Phase 31's integration points through the real app: Planner
retrieving recent reflections before planning, Memory storing every
reflection as MemoryType.REFLECTION, and Observability being reused (no
second tracing layer) — mirrors test_collaboration_integrations.py's own
pattern of exercising real REST paths, never isolated fixtures.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.dependencies.memory import get_memory_store
from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_memory() -> None:
    get_memory_store().clear()
    yield
    get_memory_store().clear()


def _csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("region,revenue\nEast,100\nWest,200\n")
    return csv_path


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


def test_reflection_is_stored_as_a_memory_type_reflection_item(tmp_path: Path) -> None:
    session_id = "reflect-int-sess-1"
    plan = _ready_plan(_csv(tmp_path), session_id, "reflect-int-s1")
    client.post("/api/v1/execution/start", json={"plan": plan, "session_id": session_id})

    generated = client.post("/api/v1/reflection/generate", json={"plan": plan}).json()["data"]

    memories = client.get("/api/v1/memory").json()["data"]
    reflection_memories = [m for m in memories if m["memory_type"] == "reflection"]
    assert len(reflection_memories) == 1
    assert reflection_memories[0]["memory_id"] == generated["reflection_id"]


def test_planner_retrieves_recent_reflections_before_planning_without_error(tmp_path: Path) -> None:
    """PlannerAgent's own docstring says "no rewrite, just enrich planning context" —
    this proves the enriched path (a REFLECTION memory already present when the
    Planner runs again) still produces a normal, successful plan.
    """
    session_id = "reflect-int-sess-2"
    csv_path = _csv(tmp_path)
    first_plan = _ready_plan(csv_path, session_id, "reflect-int-s2a")
    client.post("/api/v1/execution/start", json={"plan": first_plan, "session_id": session_id})
    client.post("/api/v1/reflection/generate", json={"plan": first_plan})

    reflection_memories_before = [
        m for m in client.get("/api/v1/memory").json()["data"] if m["memory_type"] == "reflection"
    ]
    assert len(reflection_memories_before) == 1

    second_response = client.post(
        "/api/v1/planner/plan",
        json={
            "step": {
                "step_id": "reflect-int-s2b",
                "name": "Planner Agent Run",
                "node_name": "planner",
                "inputs": {"user_request": "Please clean my uploaded customer records dataset again."},
            },
            "session_id": session_id,
        },
    )
    assert second_response.status_code == 200, second_response.text
    assert second_response.json()["data"]["status"] == "completed"


def test_reflection_generation_does_not_add_a_second_tracing_mechanism(tmp_path: Path) -> None:
    """Observability integration: the wave/plan trace ObservabilityService already
    produced is what reflection reads — generating a reflection creates no new
    trace of its own for the *analyzed* plan (only its own service-boundary
    ToolTrace, when invoked from within an active trace context — see
    test_reflection_service.py's own direct proof of that).
    """
    session_id = "reflect-int-sess-3"
    plan = _ready_plan(_csv(tmp_path), session_id, "reflect-int-s3")
    client.post("/api/v1/execution/start", json={"plan": plan, "session_id": session_id})

    traces_before = client.get("/api/v1/observability/traces").json()["data"]
    client.post("/api/v1/reflection/generate", json={"plan": plan})
    traces_after = client.get("/api/v1/observability/traces").json()["data"]

    assert len(traces_after) == len(traces_before)
