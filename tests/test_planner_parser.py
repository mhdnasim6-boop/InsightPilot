"""Tests for the JSON extractor and PlanParser."""

import json

import pytest

from backend.agents.planner.exceptions import MalformedPlanError
from backend.agents.planner.parser.json_extractor import extract_json_object
from backend.agents.planner.parser.plan_parser import PlanParser

_VALID_PLAN_JSON: dict[str, object] = {
    "goal": "Clean the dataset.",
    "reasoning_summary": "The user asked for cleaning.",
    "confidence": 0.9,
    "warnings": [],
    "assumptions": [],
    "estimated_complexity": "low",
    "estimated_duration": 10.0,
    "steps": [
        {"step_id": "s1", "name": "Ingest", "node_name": "ingestion", "dependencies": []},
        {"step_id": "s2", "name": "Clean", "node_name": "cleaning", "dependencies": ["s1"]},
    ],
}


def test_extract_json_object_from_pure_json() -> None:
    text = json.dumps({"a": 1, "b": {"c": 2}})
    assert extract_json_object(text) == text


def test_extract_json_object_ignores_surrounding_prose_and_fences() -> None:
    payload = json.dumps({"a": 1})
    text = f"Sure, here is the plan:\n```json\n{payload}\n```\nLet me know if you need anything else."
    assert extract_json_object(text) == payload


def test_extract_json_object_handles_braces_inside_strings() -> None:
    payload = json.dumps({"note": "use {curly} braces safely"})
    assert extract_json_object(f"prefix {payload} suffix") == payload


def test_extract_json_object_raises_when_no_brace_present() -> None:
    with pytest.raises(ValueError, match="No JSON object found"):
        extract_json_object("no json here at all")


def test_extract_json_object_raises_when_unbalanced() -> None:
    with pytest.raises(ValueError, match="No balanced JSON object found"):
        extract_json_object('{"a": 1, "b": 2')


def test_plan_parser_parses_a_valid_plan() -> None:
    content = f"Here you go:\n{json.dumps(_VALID_PLAN_JSON)}\nHope that helps."
    draft = PlanParser().parse(content)

    assert draft.goal == "Clean the dataset."
    assert draft.confidence == 0.9
    assert [step.step_id for step in draft.steps] == ["s1", "s2"]


def test_plan_parser_raises_malformed_plan_error_when_no_json_found() -> None:
    with pytest.raises(MalformedPlanError):
        PlanParser().parse("I cannot help with that.")


def test_plan_parser_raises_malformed_plan_error_on_unbalanced_json() -> None:
    with pytest.raises(MalformedPlanError):
        PlanParser().parse('{"goal": "incomplete"')


def test_plan_parser_raises_malformed_plan_error_on_schema_mismatch() -> None:
    bad_payload = {**_VALID_PLAN_JSON, "confidence": "not-a-number"}
    with pytest.raises(MalformedPlanError):
        PlanParser().parse(json.dumps(bad_payload))


def test_plan_parser_raises_malformed_plan_error_on_missing_required_field() -> None:
    bad_payload = dict(_VALID_PLAN_JSON)
    del bad_payload["goal"]
    with pytest.raises(MalformedPlanError):
        PlanParser().parse(json.dumps(bad_payload))


def test_plan_parser_raises_malformed_plan_error_on_invalid_complexity() -> None:
    bad_payload = {**_VALID_PLAN_JSON, "estimated_complexity": "extreme"}
    with pytest.raises(MalformedPlanError):
        PlanParser().parse(json.dumps(bad_payload))
