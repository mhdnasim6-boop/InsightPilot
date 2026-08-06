"""Unit tests for frontend.utils.chat_context — pure Chat-page helpers.

``build_chat_context`` reads ``DashboardState`` properties, which work
fine outside a real Streamlit run (see ``test_frontend_state.py``), so
this stays a plain unit test with no Streamlit widgets involved.
"""

from collections.abc import Iterator
from typing import Any

import pytest
import streamlit as st

from frontend.state.session_state import DashboardState
from frontend.utils.chat_context import (
    build_chat_context,
    find_referenced_charts,
    find_referenced_kpis,
)


@pytest.fixture(autouse=True)
def _clear_session_state() -> Iterator[None]:
    st.session_state.clear()
    yield
    st.session_state.clear()


def test_build_chat_context_includes_session_id_and_defaults() -> None:
    state = DashboardState()

    context = build_chat_context("s1", state)

    assert context["session_id"] == "s1"
    assert context["selected_dataset"] is None
    assert context["analysis_result"] is None
    assert context["visualization_result"] is None
    assert context["execution_plan"] is None
    assert context["report_document"] is None
    assert context["workflow"] is None
    assert context["reflection_result"] is None
    assert context["optimization_result"] is None
    assert context["conversation_history"] == []


def test_build_chat_context_includes_whatever_state_currently_holds() -> None:
    state = DashboardState()
    state.selected_dataset = {"dataset_id": "d1"}
    state.current_analysis = {"analysis_id": "a1"}
    state.current_plan = {"goal": "Clean the data."}
    state.add_chat_message("user", "hello")

    context = build_chat_context("s1", state)

    assert context["selected_dataset"] == {"dataset_id": "d1"}
    assert context["analysis_result"] == {"analysis_id": "a1"}
    assert context["execution_plan"] == {"goal": "Clean the data."}
    assert context["conversation_history"][0]["content"] == "hello"


def test_build_chat_context_includes_report_workflow_reflection_and_optimization() -> None:
    state = DashboardState()
    state.current_report = {"report_id": "r1"}
    state.current_workflow = {"workflow_id": "w1"}
    state.current_reflection = {"reflection_id": "ref1"}
    state.current_optimization = {"optimization_id": "opt1"}

    context = build_chat_context("s1", state)

    assert context["report_document"] == {"report_id": "r1"}
    assert context["workflow"] == {"workflow_id": "w1"}
    assert context["reflection_result"] == {"reflection_id": "ref1"}
    assert context["optimization_result"] == {"optimization_id": "opt1"}


def test_build_chat_context_unwraps_visualization_result() -> None:
    state = DashboardState()
    state.current_visualization = {"visualization_result": {"charts": []}, "rendered_charts": {}}

    context = build_chat_context("s1", state)

    assert context["visualization_result"] == {"charts": []}


def test_find_referenced_kpis_preserves_requested_order() -> None:
    kpis = [
        {"name": "Total Revenue", "value": 1000},
        {"name": "Average Revenue", "value": 100},
        {"name": "Record Count", "value": 10},
    ]

    matched = find_referenced_kpis(kpis, ["Record Count", "Total Revenue"])

    assert [kpi["name"] for kpi in matched] == ["Record Count", "Total Revenue"]


def test_find_referenced_kpis_ignores_unknown_names() -> None:
    kpis = [{"name": "Total Revenue", "value": 1000}]

    matched = find_referenced_kpis(kpis, ["Total Revenue", "Does Not Exist"])

    assert len(matched) == 1


def test_find_referenced_charts_pairs_spec_with_rendered_json() -> None:
    charts = [{"chart_id": "c1", "title": "Revenue"}, {"chart_id": "c2", "title": "Cost"}]
    rendered_charts: dict[str, dict[str, Any]] = {"c1": {"data": [], "layout": {}}, "c2": {"data": [], "layout": {}}}

    matched = find_referenced_charts(charts, rendered_charts, ["c2"])

    assert len(matched) == 1
    assert matched[0][0]["title"] == "Cost"
    assert matched[0][1] == {"data": [], "layout": {}}


def test_find_referenced_charts_skips_ids_missing_from_either_side() -> None:
    charts = [{"chart_id": "c1", "title": "Revenue"}]
    rendered_charts: dict[str, dict[str, Any]] = {"c1": {"data": [], "layout": {}}}

    matched = find_referenced_charts(charts, rendered_charts, ["c1", "c2"])

    assert len(matched) == 1
