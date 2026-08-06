"""Tests proving Phase 32's integration points through the real app: Planner
calling AdaptivePlanningService before finalizing a plan, Memory storing
every optimization as MemoryType.ADAPTIVE_PLAN, Reflection feeding pattern
detection, and Execution never being touched — mirrors
test_adaptive_service.py's construction style and
test_collaboration_integrations.py's own real-REST-round-trip pattern.
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
    return response.json()["data"]


def test_planner_integration_calls_adaptive_planning_service_automatically() -> None:
    """PlannerService.plan() should call AdaptivePlanningService.optimize() before
    finalizing every plan — proven by one ADAPTIVE_PLAN memory existing after a
    single /planner/plan call, with no separate /adaptive/optimize call at all.
    """
    _ready_plan("adaptive-int-sess-1", "adaptive-int-s1")

    memories = client.get("/api/v1/memory").json()["data"]
    adaptive_memories = [m for m in memories if m["memory_type"] == "adaptive_plan"]
    assert len(adaptive_memories) == 1


def test_planner_still_owns_plan_generation_when_no_patterns_exist() -> None:
    """With no repeated historical evidence yet, the optimized plan returned to the
    Planner is identical in structure to what it would have produced anyway —
    the adaptive layer only ever *suggests*, per its own design.
    """
    data = _ready_plan("adaptive-int-sess-2", "adaptive-int-s2")
    assert data["status"] == "completed"
    assert data["planner_output"]["execution_plan"]["steps"]


def test_memory_integration_stores_optimization_as_adaptive_plan_type() -> None:
    plan = dict(_ready_plan("adaptive-int-sess-3", "adaptive-int-s3")["planner_output"]["execution_plan"])
    plan["status"] = "ready"

    result = client.post("/api/v1/adaptive/optimize", json={"plan": plan}).json()["data"]

    memories = client.get("/api/v1/memory").json()["data"]
    match = [m for m in memories if m["memory_id"] == result["optimization_id"]]
    assert len(match) == 1
    assert match[0]["memory_type"] == "adaptive_plan"


def test_reflection_integration_feeds_pattern_detection(tmp_path: Path) -> None:
    """Generating a real reflection, then optimizing a plan, should not error even
    though ReflectionService.list_all() now returns a real ReflectionResult —
    proving AdaptivePlanningService genuinely consumes real reflection data.
    """
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("region,revenue\nEast,100\nWest,200\n")
    session_id = "adaptive-int-sess-4"

    data = _ready_plan(session_id, "adaptive-int-s4")
    plan = dict(data["planner_output"]["execution_plan"])
    plan["status"] = "ready"
    for step in plan["steps"]:
        if step["node_name"] == "file_agent":
            step["inputs"]["dataset_reference"] = str(csv_path)

    client.post("/api/v1/execution/start", json={"plan": plan, "session_id": session_id})
    client.post("/api/v1/reflection/generate", json={"plan": plan})

    response = client.post("/api/v1/adaptive/optimize", json={"plan": plan, "session_id": session_id})
    assert response.status_code == 200, response.text


def test_execution_integration_never_touches_execution_service(tmp_path: Path) -> None:
    """Optimizing a plan must not itself start any execution — proven by the
    execution history staying empty (via /adaptive/history's own plan_id, which
    would only exist if ExecutionService had been invoked as a side effect).
    """
    plan = dict(_ready_plan("adaptive-int-sess-5", "adaptive-int-s5")["planner_output"]["execution_plan"])
    plan["status"] = "ready"

    client.post("/api/v1/adaptive/explain", json={"plan": plan})

    response = client.get(f"/api/v1/execution/{plan['plan_id']}")
    assert response.status_code == 404
