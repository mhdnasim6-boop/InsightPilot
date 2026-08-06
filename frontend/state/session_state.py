"""Reusable dashboard session state.

A thin, typed wrapper over ``st.session_state``. Every getter/setter
manages exactly one state slot — there is no validation, no API calls, and
no workflow decisions here, only storage. Pages hold the JSON-shaped
``dict``/``list`` values the API client already returns; this module never
imports a backend Pydantic model.

``current_visualization`` and ``current_plan`` extend the spec's literal
tracked-field list (selected dataset, current analysis, selected charts,
current layout, theme, preferences, recent activity) for one mechanical
reason: Streamlit reruns the whole script on every widget interaction, so
whatever a page fetched from the backend must live in session state or it
is lost the moment the user touches an unrelated filter/theme widget on
the same page.
"""

from datetime import UTC, datetime
from typing import Any

import streamlit as st

from config.settings import get_settings

SESSION_ID_KEY = "dashboard_session_id"
SELECTED_DATASET_KEY = "dashboard_selected_dataset"
CURRENT_CLEANING_OUTCOME_KEY = "dashboard_current_cleaning_outcome"
CURRENT_ANALYSIS_KEY = "dashboard_current_analysis"
CURRENT_VISUALIZATION_KEY = "dashboard_current_visualization"
CURRENT_PLAN_KEY = "dashboard_current_plan"
CURRENT_PLAN_EXECUTION_KEY = "dashboard_current_plan_execution"
CURRENT_DAG_EXECUTION_KEY = "dashboard_current_dag_execution"
CURRENT_COLLABORATION_KEY = "dashboard_current_collaboration"
CURRENT_REFLECTION_KEY = "dashboard_current_reflection"
CURRENT_OPTIMIZATION_KEY = "dashboard_current_optimization"
CURRENT_WORKFLOW_KEY = "dashboard_current_workflow"
CURRENT_REPORT_KEY = "dashboard_current_report"
CURRENT_AGENT_EXECUTION_KEY = "dashboard_current_agent_execution"
CURRENT_BROWSER_EXECUTION_KEY = "dashboard_current_browser_execution"
CURRENT_REPORT_AGENT_EXECUTION_KEY = "dashboard_current_report_agent_execution"
CURRENT_EXECUTIVE_SUMMARY_EXECUTION_KEY = "dashboard_current_executive_summary_execution"
SELECTED_CHARTS_KEY = "dashboard_selected_charts"
CURRENT_LAYOUT_KEY = "dashboard_current_layout"
THEME_KEY = "dashboard_theme"
PREFERENCES_KEY = "dashboard_preferences"
RECENT_ACTIVITY_KEY = "dashboard_recent_activity"
BACKEND_URL_KEY = "dashboard_backend_url"
CHAT_HISTORY_KEY = "dashboard_chat_history"
SQL_CONNECTION_KEY = "dashboard_sql_connection"
ACCESS_TOKEN_KEY = "dashboard_access_token"
REFRESH_TOKEN_KEY = "dashboard_refresh_token"
CURRENT_USER_KEY = "dashboard_current_user"
LIVE_EVENTS_KEY = "dashboard_live_events"
LIVE_STREAM_PAUSED_KEY = "dashboard_live_stream_paused"
LIVE_FILTERS_KEY = "dashboard_live_filters"

MAX_RECENT_ACTIVITY = 20
MAX_CHAT_HISTORY = 50
MAX_LIVE_EVENTS = 200

_DEFAULT_LIVE_FILTERS: dict[str, Any] = {
    "event_types": [], "workflow_id": "", "trace_id": "", "agent_name": "",
}

_DEFAULT_PREFERENCES: dict[str, Any] = {"chart_density": "comfortable", "debug_mode": False, "advanced_mode": False}


class DashboardState:
    """Typed accessor over ``st.session_state`` for dashboard-wide UI state."""

    def __init__(self) -> None:
        st.session_state.setdefault(SESSION_ID_KEY, None)
        st.session_state.setdefault(SELECTED_DATASET_KEY, None)
        st.session_state.setdefault(CURRENT_CLEANING_OUTCOME_KEY, None)
        st.session_state.setdefault(CURRENT_ANALYSIS_KEY, None)
        st.session_state.setdefault(CURRENT_VISUALIZATION_KEY, None)
        st.session_state.setdefault(CURRENT_PLAN_KEY, None)
        st.session_state.setdefault(CURRENT_PLAN_EXECUTION_KEY, None)
        st.session_state.setdefault(CURRENT_DAG_EXECUTION_KEY, None)
        st.session_state.setdefault(CURRENT_COLLABORATION_KEY, None)
        st.session_state.setdefault(CURRENT_REFLECTION_KEY, None)
        st.session_state.setdefault(CURRENT_OPTIMIZATION_KEY, None)
        st.session_state.setdefault(CURRENT_WORKFLOW_KEY, None)
        st.session_state.setdefault(CURRENT_REPORT_KEY, None)
        st.session_state.setdefault(CURRENT_AGENT_EXECUTION_KEY, None)
        st.session_state.setdefault(CURRENT_BROWSER_EXECUTION_KEY, None)
        st.session_state.setdefault(CURRENT_REPORT_AGENT_EXECUTION_KEY, None)
        st.session_state.setdefault(CURRENT_EXECUTIVE_SUMMARY_EXECUTION_KEY, None)
        st.session_state.setdefault(SELECTED_CHARTS_KEY, [])
        st.session_state.setdefault(CURRENT_LAYOUT_KEY, "detailed_analysis")
        st.session_state.setdefault(THEME_KEY, "light")
        st.session_state.setdefault(PREFERENCES_KEY, dict(_DEFAULT_PREFERENCES))
        st.session_state.setdefault(RECENT_ACTIVITY_KEY, [])
        st.session_state.setdefault(BACKEND_URL_KEY, get_settings().backend_url)
        st.session_state.setdefault(CHAT_HISTORY_KEY, [])
        st.session_state.setdefault(SQL_CONNECTION_KEY, None)
        st.session_state.setdefault(ACCESS_TOKEN_KEY, None)
        st.session_state.setdefault(REFRESH_TOKEN_KEY, None)
        st.session_state.setdefault(CURRENT_USER_KEY, None)
        st.session_state.setdefault(LIVE_EVENTS_KEY, [])
        st.session_state.setdefault(LIVE_STREAM_PAUSED_KEY, False)
        st.session_state.setdefault(LIVE_FILTERS_KEY, dict(_DEFAULT_LIVE_FILTERS))

    # -- Session --------------------------------------------------------------

    @property
    def session_id(self) -> str | None:
        return st.session_state[SESSION_ID_KEY]

    @session_id.setter
    def session_id(self, value: str | None) -> None:
        st.session_state[SESSION_ID_KEY] = value

    # -- Dataset / analysis / visualization / plan -----------------------------

    @property
    def selected_dataset(self) -> dict[str, Any] | None:
        return st.session_state[SELECTED_DATASET_KEY]

    @selected_dataset.setter
    def selected_dataset(self, value: dict[str, Any] | None) -> None:
        st.session_state[SELECTED_DATASET_KEY] = value

    @property
    def current_cleaning_outcome(self) -> dict[str, Any] | None:
        """The last ``CleaningOutcome`` fetched — the Analysis page's request body."""
        return st.session_state[CURRENT_CLEANING_OUTCOME_KEY]

    @current_cleaning_outcome.setter
    def current_cleaning_outcome(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_CLEANING_OUTCOME_KEY] = value

    @property
    def current_analysis(self) -> dict[str, Any] | None:
        return st.session_state[CURRENT_ANALYSIS_KEY]

    @current_analysis.setter
    def current_analysis(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_ANALYSIS_KEY] = value

    @property
    def current_visualization(self) -> dict[str, Any] | None:
        return st.session_state[CURRENT_VISUALIZATION_KEY]

    @current_visualization.setter
    def current_visualization(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_VISUALIZATION_KEY] = value

    @property
    def current_plan(self) -> dict[str, Any] | None:
        return st.session_state[CURRENT_PLAN_KEY]

    @current_plan.setter
    def current_plan(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_PLAN_KEY] = value

    @property
    def current_plan_execution(self) -> dict[str, Any] | None:
        """The last ExecutionPlan returned by execute/resume/reject/cancel (Human-in-the-Loop).

        Distinct from ``current_plan`` (the freshly-*generated*,
        not-yet-approved plan): this tracks whatever is currently
        running/paused, so Approval Status/Resume/Reject/Cancel controls
        survive an unrelated widget interaction on the same page.
        """
        return st.session_state[CURRENT_PLAN_EXECUTION_KEY]

    @current_plan_execution.setter
    def current_plan_execution(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_PLAN_EXECUTION_KEY] = value

    @property
    def current_dag_execution(self) -> dict[str, Any] | None:
        """The last ExecutionState returned by start/resume/cancel (the parallel DAG engine).

        Distinct from ``current_plan_execution`` (the sequential
        ``PlanExecutor`` path) — this tracks whatever DAG execution is
        currently running/paused via ``ExecutionService``, so the
        Execution page's progress/graph/controls survive an unrelated
        widget interaction on the same page.
        """
        return st.session_state[CURRENT_DAG_EXECUTION_KEY]

    @current_dag_execution.setter
    def current_dag_execution(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_DAG_EXECUTION_KEY] = value

    @property
    def current_collaboration(self) -> dict[str, Any] | None:
        """The last CollaborationTask returned by start/delegate/run/resume/cancel.

        Mirrors ``current_dag_execution``'s own reasoning: whatever the
        Collaboration page fetched from the backend must survive an
        unrelated widget interaction on the same page.
        """
        return st.session_state[CURRENT_COLLABORATION_KEY]

    @current_collaboration.setter
    def current_collaboration(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_COLLABORATION_KEY] = value

    @property
    def current_reflection(self) -> dict[str, Any] | None:
        """The last ReflectionResult returned by generate() — survives an unrelated widget interaction."""
        return st.session_state[CURRENT_REFLECTION_KEY]

    @current_reflection.setter
    def current_reflection(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_REFLECTION_KEY] = value

    @property
    def current_optimization(self) -> dict[str, Any] | None:
        """The last OptimizationResult returned by optimize()/explain() — survives an unrelated widget interaction."""
        return st.session_state[CURRENT_OPTIMIZATION_KEY]

    @current_optimization.setter
    def current_optimization(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_OPTIMIZATION_KEY] = value

    @property
    def current_workflow(self) -> dict[str, Any] | None:
        """The last Workflow created/selected on the Workflows page — survives an unrelated widget interaction."""
        return st.session_state[CURRENT_WORKFLOW_KEY]

    @current_workflow.setter
    def current_workflow(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_WORKFLOW_KEY] = value

    @property
    def current_agent_execution(self) -> dict[str, Any] | None:
        """The last FileAgent AgentExecutionResult — the Planning page's own display state."""
        return st.session_state[CURRENT_AGENT_EXECUTION_KEY]

    @current_agent_execution.setter
    def current_agent_execution(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_AGENT_EXECUTION_KEY] = value

    @property
    def current_browser_execution(self) -> dict[str, Any] | None:
        """The last BrowserAgentResult — a different shape than ``current_agent_execution``
        (sources/summaries, not dataset/analysis/report), so it gets its own slot."""
        return st.session_state[CURRENT_BROWSER_EXECUTION_KEY]

    @current_browser_execution.setter
    def current_browser_execution(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_BROWSER_EXECUTION_KEY] = value

    @property
    def current_report_agent_execution(self) -> dict[str, Any] | None:
        """The last ReportAgentResult — a different shape again (report_id/report_document/
        warnings/execution_time), so it gets its own slot too. Its ``report_document`` is
        also mirrored into ``current_report`` on success, reusing the Reports page's own
        preview/export UI rather than duplicating it here."""
        return st.session_state[CURRENT_REPORT_AGENT_EXECUTION_KEY]

    @current_report_agent_execution.setter
    def current_report_agent_execution(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_REPORT_AGENT_EXECUTION_KEY] = value

    @property
    def current_executive_summary_execution(self) -> dict[str, Any] | None:
        """The last ExecutiveSummaryResult — a different shape again (executive_summary/
        key_findings/risks/recommendations/follow_up_actions/confidence), so it gets its
        own slot too. Its source ``report_document`` is whatever is in ``current_report``
        at the time it was generated - reusing the Reports page's own preview UI for that,
        rather than duplicating it here."""
        return st.session_state[CURRENT_EXECUTIVE_SUMMARY_EXECUTION_KEY]

    @current_executive_summary_execution.setter
    def current_executive_summary_execution(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_EXECUTIVE_SUMMARY_EXECUTION_KEY] = value

    @property
    def current_report(self) -> dict[str, Any] | None:
        """The last generated ``ReportDocument`` — the Reports page's own display state."""
        return st.session_state[CURRENT_REPORT_KEY]

    @current_report.setter
    def current_report(self, value: dict[str, Any] | None) -> None:
        st.session_state[CURRENT_REPORT_KEY] = value

    # -- Charts / layout / theme ------------------------------------------------

    @property
    def selected_charts(self) -> list[str]:
        return list(st.session_state[SELECTED_CHARTS_KEY])

    @selected_charts.setter
    def selected_charts(self, value: list[str]) -> None:
        st.session_state[SELECTED_CHARTS_KEY] = list(value)

    @property
    def current_layout(self) -> str:
        return str(st.session_state[CURRENT_LAYOUT_KEY])

    @current_layout.setter
    def current_layout(self, value: str) -> None:
        st.session_state[CURRENT_LAYOUT_KEY] = value

    @property
    def theme(self) -> str:
        return str(st.session_state[THEME_KEY])

    @theme.setter
    def theme(self, value: str) -> None:
        st.session_state[THEME_KEY] = value

    # -- Preferences --------------------------------------------------------

    @property
    def preferences(self) -> dict[str, Any]:
        return dict(st.session_state[PREFERENCES_KEY])

    def update_preferences(self, **kwargs: Any) -> None:
        """Merge the given keys into the stored preferences dict."""
        st.session_state[PREFERENCES_KEY] = {**st.session_state[PREFERENCES_KEY], **kwargs}

    @property
    def chart_density(self) -> str:
        return str(self.preferences.get("chart_density", "comfortable"))

    @chart_density.setter
    def chart_density(self, value: str) -> None:
        self.update_preferences(chart_density=value)

    @property
    def debug_mode(self) -> bool:
        return bool(self.preferences.get("debug_mode", False))

    @debug_mode.setter
    def debug_mode(self, value: bool) -> None:
        self.update_preferences(debug_mode=value)

    @property
    def advanced_mode(self) -> bool:
        """Whether the sidebar's Advanced section (engineering-oriented pages —
        Plugins, Distributed, Federation, Observability, ...) is revealed. A pure
        product/IA preference, not a security control: the underlying pages are
        still reachable by direct URL and still enforce their own real
        permissions server-side regardless of this flag."""
        return bool(self.preferences.get("advanced_mode", False))

    @advanced_mode.setter
    def advanced_mode(self, value: bool) -> None:
        self.update_preferences(advanced_mode=value)

    # -- Backend URL --------------------------------------------------------

    @property
    def backend_url(self) -> str:
        return str(st.session_state[BACKEND_URL_KEY])

    @backend_url.setter
    def backend_url(self, value: str) -> None:
        st.session_state[BACKEND_URL_KEY] = value

    # -- Recent activity ------------------------------------------------------

    @property
    def recent_activity(self) -> list[dict[str, Any]]:
        return list(st.session_state[RECENT_ACTIVITY_KEY])

    def add_activity(self, message: str) -> None:
        """Prepend a timestamped activity entry, capped at the most recent entries."""
        entry = {"timestamp": datetime.now(UTC).isoformat(), "message": message}
        activity = [entry, *st.session_state[RECENT_ACTIVITY_KEY]][:MAX_RECENT_ACTIVITY]
        st.session_state[RECENT_ACTIVITY_KEY] = activity

    # -- Chat -----------------------------------------------------------------

    @property
    def chat_history(self) -> list[dict[str, Any]]:
        """The conversation so far, oldest first — shaped like the backend's ``ChatMessage``.

        Held here (not on the backend) because conversation memory is out
        of scope for this phase: every chat request echoes this list back
        as ``ChatContext.conversation_history``, and the backend never
        stores it itself. Assistant entries may carry extra display-only
        keys (``referenced_kpis``, ``referenced_charts``, ...) — the
        backend's ``ChatMessage`` only reads ``role``/``content``/
        ``timestamp`` and silently ignores the rest (Pydantic v2's
        default), so it's safe to echo these richer dicts back untouched.
        """
        return list(st.session_state[CHAT_HISTORY_KEY])

    def add_chat_message(self, role: str, content: str, **extra: Any) -> None:
        """Append one turn to the conversation, oldest first, capped at the most recent entries."""
        entry = {"role": role, "content": content, "timestamp": datetime.now(UTC).isoformat(), **extra}
        history = [*st.session_state[CHAT_HISTORY_KEY], entry][-MAX_CHAT_HISTORY:]
        st.session_state[CHAT_HISTORY_KEY] = history

    def clear_chat_history(self) -> None:
        """Clear the conversation, starting fresh."""
        st.session_state[CHAT_HISTORY_KEY] = []

    # -- SQL connection ---------------------------------------------------------

    @property
    def sql_connection(self) -> dict[str, Any] | None:
        """The SQL connection config currently in use on the SQL page — including its password.

        Kept in its own, narrowly-scoped slot (never merged into
        ``preferences``/``metadata``/logged into ``recent_activity``) so a
        credential only ever flows through the one page that needs it.
        """
        return st.session_state[SQL_CONNECTION_KEY]

    @sql_connection.setter
    def sql_connection(self, value: dict[str, Any] | None) -> None:
        st.session_state[SQL_CONNECTION_KEY] = value

    # -- Authentication (Phase 35) --------------------------------------------------

    @property
    def access_token(self) -> str | None:
        return st.session_state[ACCESS_TOKEN_KEY]

    @property
    def refresh_token(self) -> str | None:
        return st.session_state[REFRESH_TOKEN_KEY]

    @property
    def current_user(self) -> dict[str, Any] | None:
        """The logged-in user's own profile (from LoginResponse.user / GET /me), or None
        if nobody is logged in — the single source ``is_authenticated`` reads."""
        return st.session_state[CURRENT_USER_KEY]

    @property
    def is_authenticated(self) -> bool:
        return st.session_state[ACCESS_TOKEN_KEY] is not None and st.session_state[CURRENT_USER_KEY] is not None

    def set_authenticated_session(self, access_token: str, refresh_token: str, user: dict[str, Any]) -> None:
        """Store a fresh login/refresh result. The one place that writes all three auth slots together."""
        st.session_state[ACCESS_TOKEN_KEY] = access_token
        st.session_state[REFRESH_TOKEN_KEY] = refresh_token
        st.session_state[CURRENT_USER_KEY] = user

    def clear_authenticated_session(self) -> None:
        """Log out locally — clears the token/user slots. Does not itself call the backend."""
        st.session_state[ACCESS_TOKEN_KEY] = None
        st.session_state[REFRESH_TOKEN_KEY] = None
        st.session_state[CURRENT_USER_KEY] = None

    # -- Live event stream (Phase 37) -------------------------------------------------

    @property
    def live_events(self) -> list[dict[str, Any]]:
        """Every event received so far this session, most recent first."""
        return list(st.session_state[LIVE_EVENTS_KEY])

    def add_live_events(self, envelopes: list[dict[str, Any]]) -> None:
        """Prepend newly received envelopes (deduped by sequence), capped at the most recent."""
        existing_sequences = {e["sequence"] for e in st.session_state[LIVE_EVENTS_KEY]}
        fresh = [e for e in envelopes if e["sequence"] not in existing_sequences]
        merged = [*reversed(fresh), *st.session_state[LIVE_EVENTS_KEY]]
        st.session_state[LIVE_EVENTS_KEY] = merged[:MAX_LIVE_EVENTS]

    def clear_live_events(self) -> None:
        st.session_state[LIVE_EVENTS_KEY] = []

    @property
    def live_stream_paused(self) -> bool:
        return bool(st.session_state[LIVE_STREAM_PAUSED_KEY])

    @live_stream_paused.setter
    def live_stream_paused(self, value: bool) -> None:
        st.session_state[LIVE_STREAM_PAUSED_KEY] = value

    @property
    def live_filters(self) -> dict[str, Any]:
        return dict(st.session_state[LIVE_FILTERS_KEY])

    @live_filters.setter
    def live_filters(self, value: dict[str, Any]) -> None:
        st.session_state[LIVE_FILTERS_KEY] = value


def get_dashboard_state() -> DashboardState:
    """Return a ``DashboardState`` bound to the current Streamlit session.

    The single call site every page should use — initializes defaults on
    first use and is a no-op on subsequent reruns.
    """
    return DashboardState()
