"""Tests for plan visualization: Mermaid, JSON export, and timeline."""

import json

from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.planning.visualization.json_export import generate_plan_json
from backend.planning.visualization.mermaid import generate_plan_mermaid
from backend.planning.visualization.timeline import generate_plan_timeline
from backend.utils.time import utc_now


def _step(step_id: str, dependencies: list[str] | None = None) -> ExecutionStep:
    return ExecutionStep(step_id=step_id, name=f"Step {step_id}", node_name="planner", dependencies=dependencies or [])


def _plan(steps: list[ExecutionStep]) -> ExecutionPlan:
    now = utc_now()
    return ExecutionPlan(plan_id="p1", created_at=now, updated_at=now, steps=steps)


def test_generate_plan_mermaid_contains_nodes_and_edges() -> None:
    plan = _plan([_step("a"), _step("b", dependencies=["a"])])

    mermaid = generate_plan_mermaid(plan)

    assert "graph TD;" in mermaid
    assert "a" in mermaid
    assert "b" in mermaid
    assert "a --> b" in mermaid


def test_generate_plan_mermaid_is_deterministic() -> None:
    plan = _plan([_step("a"), _step("b", dependencies=["a"])])
    assert generate_plan_mermaid(plan) == generate_plan_mermaid(plan)


def test_generate_plan_json_round_trips_plan_id_and_steps() -> None:
    plan = _plan([_step("a"), _step("b", dependencies=["a"])])

    raw = generate_plan_json(plan)
    data = json.loads(raw)

    assert data["plan_id"] == "p1"
    assert [step["step_id"] for step in data["steps"]] == ["a", "b"]


def test_generate_plan_timeline_reflects_execution_order() -> None:
    plan = _plan([_step("b", dependencies=["a"]), _step("a")])

    timeline = generate_plan_timeline(plan, execution_order=["a", "b"])

    assert timeline.plan_id == "p1"
    assert [entry.step_id for entry in timeline.entries] == ["a", "b"]
    assert timeline.entries[0].order_index == 0
    assert timeline.entries[1].depends_on == ["a"]


def test_generate_plan_timeline_defaults_to_declaration_order() -> None:
    plan = _plan([_step("b", dependencies=["a"]), _step("a")])
    timeline = generate_plan_timeline(plan)
    assert [entry.step_id for entry in timeline.entries] == ["b", "a"]
