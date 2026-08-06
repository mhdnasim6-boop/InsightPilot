"""Unit tests for frontend.utils.suggested_prompts.generate_starter_prompts — pure
formatting over already-fetched DashboardState dicts, no Streamlit widgets involved.
"""

from collections.abc import Iterator

import pytest
import streamlit as st

from frontend.state.session_state import DashboardState
from frontend.utils.suggested_prompts import GENERIC_STARTERS, generate_starter_prompts


@pytest.fixture(autouse=True)
def _clear_session_state() -> Iterator[None]:
    st.session_state.clear()
    yield
    st.session_state.clear()


def test_falls_back_to_generic_starters_with_no_data() -> None:
    state = DashboardState()
    assert generate_starter_prompts(state) == GENERIC_STARTERS


def test_includes_a_kpi_specific_suggestion_when_analysis_has_kpis() -> None:
    state = DashboardState()
    state.current_analysis = {"kpis": [{"name": "Total Revenue"}]}

    prompts = generate_starter_prompts(state)

    assert "What's driving Total Revenue?" in prompts


def test_includes_anomaly_suggestion_only_when_anomalies_are_applicable_and_present() -> None:
    state = DashboardState()
    state.current_analysis = {"kpis": [], "anomalies": {"applicable": True, "columns": ["revenue"]}}
    assert "Explain the anomalies you found." in generate_starter_prompts(state)

    state.current_analysis = {"kpis": [], "anomalies": {"applicable": False, "columns": []}}
    assert "Explain the anomalies you found." not in generate_starter_prompts(state)


def test_includes_report_suggestion_when_a_report_exists() -> None:
    state = DashboardState()
    state.current_report = {"report_id": "r1", "title": "Sales Report"}
    assert "Summarize this report." in generate_starter_prompts(state)


def test_includes_workflow_suggestion_naming_the_workflow() -> None:
    state = DashboardState()
    state.current_workflow = {"workflow_id": "w1", "definition": {"name": "Sales Pipeline"}}

    prompts = generate_starter_prompts(state)

    assert "What's the status of the 'Sales Pipeline' workflow?" in prompts
    assert any("workflow" in prompt.lower() for prompt in prompts)


def test_includes_reflection_suggestion_when_a_reflection_exists() -> None:
    state = DashboardState()
    state.current_reflection = {"reflection_id": "ref1"}
    assert "What's the reflection on this execution?" in generate_starter_prompts(state)


def test_includes_optimization_suggestion_when_an_optimization_exists() -> None:
    state = DashboardState()
    state.current_optimization = {"optimization_id": "opt1"}
    assert "What did the optimizer suggest?" in generate_starter_prompts(state)


def test_never_returns_more_than_four_suggestions() -> None:
    state = DashboardState()
    state.current_analysis = {"kpis": [{"name": "Total Revenue"}], "anomalies": {"applicable": True, "columns": ["x"]}}
    state.current_visualization = {"visualization_result": {"charts": []}, "rendered_charts": {}}
    state.current_report = {"report_id": "r1"}
    state.current_workflow = {"workflow_id": "w1", "definition": {"name": "Pipeline"}}
    state.current_reflection = {"reflection_id": "ref1"}
    state.current_optimization = {"optimization_id": "opt1"}

    assert len(generate_starter_prompts(state)) <= 4


def test_deduplicates_while_preserving_order() -> None:
    state = DashboardState()
    state.current_report = {"report_id": "r1"}

    prompts = generate_starter_prompts(state)

    assert len(prompts) == len(set(prompts))
