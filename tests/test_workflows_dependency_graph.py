"""Tests for WorkflowDependencyGraph: ordering, cycle detection, parallel
batching, and dynamic insert/remove — all reusing topological_order()."""

import pytest

from backend.workflows.coordination.dependency_graph import (
    WorkflowDependencyGraph,
    to_execution_steps,
)
from backend.workflows.exceptions import WorkflowCycleError
from backend.workflows.models.workflow_step import WorkflowStep


def _step(step_id: str, dependencies: list[str] | None = None) -> WorkflowStep:
    return WorkflowStep(step_id=step_id, name=step_id, node_name="file_agent", dependencies=dependencies or [])


def test_to_execution_steps_is_a_lossless_structural_mapping() -> None:
    steps = [_step("a"), _step("b", ["a"])]
    execution_steps = to_execution_steps(steps)
    assert [s.step_id for s in execution_steps] == ["a", "b"]
    assert execution_steps[1].dependencies == ["a"]


def test_order_returns_a_valid_topological_order() -> None:
    steps = [_step("b", ["a"]), _step("a")]
    order = WorkflowDependencyGraph().order(steps)
    assert order == ["a", "b"]


def test_order_raises_workflow_cycle_error_for_a_cycle() -> None:
    steps = [_step("a", ["b"]), _step("b", ["a"])]
    with pytest.raises(WorkflowCycleError):
        WorkflowDependencyGraph().order(steps)


def test_order_is_deterministic_for_independent_steps() -> None:
    steps = [_step("z"), _step("a"), _step("m")]
    assert WorkflowDependencyGraph().order(steps) == ["a", "m", "z"]


def test_parallel_batches_groups_independent_steps_together() -> None:
    steps = [_step("a"), _step("b"), _step("c", ["a", "b"])]
    batches = WorkflowDependencyGraph().parallel_batches(steps)
    assert batches == [["a", "b"], ["c"]]


def test_parallel_batches_raises_for_a_cycle() -> None:
    steps = [_step("a", ["b"]), _step("b", ["a"])]
    with pytest.raises(WorkflowCycleError):
        WorkflowDependencyGraph().parallel_batches(steps)


def test_validate_dependencies_finds_a_missing_reference() -> None:
    steps = [_step("a", ["ghost"])]
    assert WorkflowDependencyGraph().validate_dependencies(steps) == ["ghost"]


def test_validate_dependencies_is_empty_when_all_present() -> None:
    steps = [_step("a"), _step("b", ["a"])]
    assert WorkflowDependencyGraph().validate_dependencies(steps) == []


def test_insert_step_adds_a_new_step() -> None:
    steps = [_step("a")]
    updated = WorkflowDependencyGraph().insert_step(steps, _step("b", ["a"]))
    assert {s.step_id for s in updated} == {"a", "b"}


def test_insert_step_replaces_an_existing_step_with_the_same_id() -> None:
    steps = [_step("a"), _step("b", ["a"])]
    replacement = _step("b", [])
    updated = WorkflowDependencyGraph().insert_step(steps, replacement)
    b = next(s for s in updated if s.step_id == "b")
    assert b.dependencies == []


def test_insert_step_raises_if_it_would_create_a_cycle() -> None:
    steps = [_step("a", ["b"]), _step("b")]
    with pytest.raises(WorkflowCycleError):
        WorkflowDependencyGraph().insert_step(steps, _step("b", ["a"]))


def test_remove_step_removes_it_and_strips_dangling_dependencies() -> None:
    steps = [_step("a"), _step("b", ["a"]), _step("c", ["a", "b"])]
    updated = WorkflowDependencyGraph().remove_step(steps, "a")
    ids = {s.step_id for s in updated}
    assert ids == {"b", "c"}
    b = next(s for s in updated if s.step_id == "b")
    c = next(s for s in updated if s.step_id == "c")
    assert b.dependencies == []
    assert c.dependencies == ["b"]
