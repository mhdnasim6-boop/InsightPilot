"""Unit tests for frontend.state.session_state.DashboardState.

``st.session_state`` behaves as a plain in-process dict when there is no
real Streamlit script run (confirmed empirically — it logs a "missing
ScriptRunContext" warning but functions normally), which is what makes
``DashboardState`` unit-testable at all. Since it is a process-wide
singleton, every test clears it first for isolation.
"""

from collections.abc import Iterator

import pytest
import streamlit as st

from frontend.state.session_state import (
    MAX_CHAT_HISTORY,
    MAX_RECENT_ACTIVITY,
    DashboardState,
    get_dashboard_state,
)


@pytest.fixture(autouse=True)
def _clear_session_state() -> Iterator[None]:
    st.session_state.clear()
    yield
    st.session_state.clear()


def test_defaults_are_applied_on_first_use() -> None:
    state = DashboardState()

    assert state.session_id is None
    assert state.selected_dataset is None
    assert state.current_cleaning_outcome is None
    assert state.current_analysis is None
    assert state.current_visualization is None
    assert state.current_plan is None
    assert state.current_plan_execution is None
    assert state.current_dag_execution is None
    assert state.current_collaboration is None
    assert state.current_reflection is None
    assert state.current_optimization is None
    assert state.current_report is None
    assert state.current_agent_execution is None
    assert state.current_browser_execution is None
    assert state.current_report_agent_execution is None
    assert state.current_executive_summary_execution is None
    assert state.selected_charts == []
    assert state.current_layout == "detailed_analysis"
    assert state.theme == "light"
    assert state.preferences == {"chart_density": "comfortable", "debug_mode": False, "advanced_mode": False}
    assert state.recent_activity == []
    assert state.backend_url  # populated from config.settings.get_settings()


def test_second_construction_does_not_reset_existing_values() -> None:
    state = DashboardState()
    state.theme = "dark"
    state.session_id = "abc"

    same_session_state = DashboardState()

    assert same_session_state.theme == "dark"
    assert same_session_state.session_id == "abc"


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("session_id", "session-1"),
        ("selected_dataset", {"dataset_id": "d1"}),
        ("current_cleaning_outcome", {"dataset": {}, "result": {}}),
        ("current_analysis", {"analysis_id": "a1"}),
        ("current_visualization", {"visualization_result": {}}),
        ("current_plan", {"goal": "test"}),
        ("current_plan_execution", {"plan_id": "p1", "status": "paused"}),
        ("current_dag_execution", {"execution_id": "e1", "status": "running"}),
        ("current_collaboration", {"collaboration_id": "c1", "status": "running"}),
        ("current_reflection", {"reflection_id": "r1", "plan_id": "p1"}),
        ("current_optimization", {"optimization_id": "o1", "plan_id": "p1"}),
        ("current_report", {"report_id": "r1"}),
        ("current_agent_execution", {"step_id": "s1", "status": "completed"}),
        ("current_browser_execution", {"step_id": "s1", "status": "completed", "sources": []}),
        ("current_report_agent_execution", {"step_id": "s1", "status": "completed", "report_id": "r1"}),
        (
            "current_executive_summary_execution",
            {"step_id": "s1", "status": "completed", "executive_summary": "Summary text."},
        ),
        ("selected_charts", ["chart-1", "chart-2"]),
        ("current_layout", "kpi_dashboard"),
        ("theme", "dark"),
        ("backend_url", "http://example.com:9000"),
    ],
)
def test_property_round_trips(attribute: str, value: object) -> None:
    state = DashboardState()
    setattr(state, attribute, value)
    assert getattr(state, attribute) == value


def test_update_preferences_merges_without_clobbering_other_keys() -> None:
    state = DashboardState()
    state.update_preferences(chart_density="compact")
    assert state.preferences == {"chart_density": "compact", "debug_mode": False, "advanced_mode": False}

    state.update_preferences(debug_mode=True)
    assert state.preferences == {"chart_density": "compact", "debug_mode": True, "advanced_mode": False}


def test_chart_density_and_debug_mode_round_trip_through_preferences() -> None:
    state = DashboardState()
    state.chart_density = "spacious"
    state.debug_mode = True

    assert state.chart_density == "spacious"
    assert state.debug_mode is True
    assert state.preferences == {"chart_density": "spacious", "debug_mode": True, "advanced_mode": False}


def test_advanced_mode_defaults_false_and_round_trips_through_preferences() -> None:
    state = DashboardState()
    assert state.advanced_mode is False

    state.advanced_mode = True
    assert state.advanced_mode is True
    assert state.preferences == {"chart_density": "comfortable", "debug_mode": False, "advanced_mode": True}


def test_add_activity_prepends_most_recent_first() -> None:
    state = DashboardState()
    state.add_activity("first")
    state.add_activity("second")

    messages = [entry["message"] for entry in state.recent_activity]
    assert messages == ["second", "first"]


def test_add_activity_caps_at_max_recent_activity() -> None:
    state = DashboardState()
    for i in range(MAX_RECENT_ACTIVITY + 5):
        state.add_activity(f"activity-{i}")

    assert len(state.recent_activity) == MAX_RECENT_ACTIVITY
    assert state.recent_activity[0]["message"] == f"activity-{MAX_RECENT_ACTIVITY + 4}"


def test_get_dashboard_state_returns_functioning_instance() -> None:
    state = get_dashboard_state()
    state.theme = "corporate"

    assert get_dashboard_state().theme == "corporate"


def test_add_chat_message_appends_oldest_first() -> None:
    state = DashboardState()
    state.add_chat_message("user", "What are the KPIs?")
    state.add_chat_message("assistant", "You have 3 KPIs.")

    roles = [message["role"] for message in state.chat_history]
    assert roles == ["user", "assistant"]


def test_add_chat_message_stores_extra_metadata_on_assistant_messages() -> None:
    state = DashboardState()
    state.add_chat_message("assistant", "You have 3 KPIs.", referenced_kpis=["Total Revenue"], confidence=1.0)

    message = state.chat_history[0]
    assert message["referenced_kpis"] == ["Total Revenue"]
    assert message["confidence"] == 1.0


def test_add_chat_message_caps_at_max_chat_history() -> None:
    state = DashboardState()
    for i in range(MAX_CHAT_HISTORY + 5):
        state.add_chat_message("user", f"question {i}")

    assert len(state.chat_history) == MAX_CHAT_HISTORY
    assert state.chat_history[-1]["content"] == f"question {MAX_CHAT_HISTORY + 4}"
    assert state.chat_history[0]["content"] == "question 5"


def test_clear_chat_history_empties_the_conversation() -> None:
    state = DashboardState()
    state.add_chat_message("user", "hello")

    state.clear_chat_history()

    assert state.chat_history == []


def test_sql_connection_defaults_to_none() -> None:
    state = DashboardState()
    assert state.sql_connection is None


def test_sql_connection_round_trips() -> None:
    state = DashboardState()
    connection = {"database_type": "sqlite", "database": "/tmp/data.db"}

    state.sql_connection = connection

    assert state.sql_connection == connection


def test_auth_defaults_to_unauthenticated() -> None:
    state = DashboardState()
    assert state.access_token is None
    assert state.refresh_token is None
    assert state.current_user is None
    assert state.is_authenticated is False


def test_set_authenticated_session_stores_all_three_slots() -> None:
    state = DashboardState()
    user = {"username": "alice", "role": "admin"}

    state.set_authenticated_session("access-1", "refresh-1", user)

    assert state.access_token == "access-1"
    assert state.refresh_token == "refresh-1"
    assert state.current_user == user
    assert state.is_authenticated is True


def test_clear_authenticated_session_resets_all_three_slots() -> None:
    state = DashboardState()
    state.set_authenticated_session("access-1", "refresh-1", {"username": "alice"})

    state.clear_authenticated_session()

    assert state.access_token is None
    assert state.refresh_token is None
    assert state.current_user is None
    assert state.is_authenticated is False


def test_current_workflow_defaults_to_none() -> None:
    state = DashboardState()
    assert state.current_workflow is None


def test_current_workflow_round_trips() -> None:
    state = DashboardState()
    workflow = {"workflow_id": "w1", "definition": {"name": "Test"}}

    state.current_workflow = workflow

    assert state.current_workflow == workflow


def test_live_events_default_to_empty() -> None:
    state = DashboardState()
    assert state.live_events == []


def test_add_live_events_prepends_most_recent_first() -> None:
    state = DashboardState()
    state.add_live_events([{"sequence": 1, "event": {}}, {"sequence": 2, "event": {}}])
    state.add_live_events([{"sequence": 3, "event": {}}])

    assert [e["sequence"] for e in state.live_events] == [3, 2, 1]


def test_add_live_events_dedupes_by_sequence() -> None:
    state = DashboardState()
    state.add_live_events([{"sequence": 1, "event": {}}])
    state.add_live_events([{"sequence": 1, "event": {}}, {"sequence": 2, "event": {}}])

    assert [e["sequence"] for e in state.live_events] == [2, 1]


def test_clear_live_events_empties_the_buffer() -> None:
    state = DashboardState()
    state.add_live_events([{"sequence": 1, "event": {}}])

    state.clear_live_events()

    assert state.live_events == []


def test_live_stream_paused_defaults_to_false_and_round_trips() -> None:
    state = DashboardState()
    assert state.live_stream_paused is False

    state.live_stream_paused = True

    assert state.live_stream_paused is True


def test_live_filters_default_and_round_trip() -> None:
    state = DashboardState()
    assert state.live_filters == {"event_types": [], "workflow_id": "", "trace_id": "", "agent_name": ""}

    state.live_filters = {"event_types": ["tool_started"], "workflow_id": "w1", "trace_id": "", "agent_name": ""}

    assert state.live_filters["event_types"] == ["tool_started"]
    assert state.live_filters["workflow_id"] == "w1"
