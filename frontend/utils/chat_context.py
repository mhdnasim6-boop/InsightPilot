"""Pure helpers for the Chat page: assembling the backend request payload and
looking up which KPIs/charts a response referenced.

None of this touches the network or Streamlit widgets — it only shapes
plain dicts already held in :class:`~frontend.state.session_state.DashboardState`.
"""

from typing import Any

from frontend.state.session_state import DashboardState


def build_chat_context(session_id: str, state: DashboardState) -> dict[str, Any]:
    """Assemble one ``ChatContext`` payload for ``session_id`` from the dashboard's current state.

    Sent fresh on every request — the backend has no server-side memory
    of the conversation, so ``conversation_history`` (from
    ``state.chat_history``) is the entire continuity between turns.

    ``report_document``/``workflow``/``reflection_result``/``optimization_result``
    extend the original field list: whatever the Reports/Workflows/
    Reflection/Adaptive pages most recently stored in session state is
    passed straight through, unchanged, the same way ``current_analysis``/
    ``current_plan`` already were — so a user can ask about the report,
    workflow, reflection, or optimization they were just looking at
    without leaving Chat or re-explaining it.
    """
    visualization = state.current_visualization or {}
    return {
        "session_id": session_id,
        "selected_dataset": state.selected_dataset,
        "cleaning_outcome": state.current_cleaning_outcome,
        "analysis_result": state.current_analysis,
        "visualization_result": visualization.get("visualization_result"),
        "execution_plan": state.current_plan,
        "report_document": state.current_report,
        "workflow": state.current_workflow,
        "reflection_result": state.current_reflection,
        "optimization_result": state.current_optimization,
        "conversation_history": state.chat_history,
        "user_preferences": state.preferences,
    }


def find_referenced_kpis(kpis: list[dict[str, Any]], names: list[str]) -> list[dict[str, Any]]:
    """Return the KPI dicts named in ``names``, in ``names``' order."""
    by_name = {kpi["name"]: kpi for kpi in kpis}
    return [by_name[name] for name in names if name in by_name]


def find_referenced_charts(
    charts: list[dict[str, Any]], rendered_charts: dict[str, dict[str, Any]], chart_ids: list[str]
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return (chart spec, rendered figure JSON) pairs for each id in ``chart_ids``."""
    by_id = {chart["chart_id"]: chart for chart in charts}
    return [
        (by_id[chart_id], rendered_charts[chart_id])
        for chart_id in chart_ids
        if chart_id in by_id and chart_id in rendered_charts
    ]
