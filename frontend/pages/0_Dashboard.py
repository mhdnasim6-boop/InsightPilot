"""Dashboard page: the new landing page — an executive workspace, not an
engineering console. Recent datasets/reports/workflows, quick actions, an AI
nudge grounded in whatever analysis already exists, and a compact system
status line.

Every fact here is either already fetched by an existing, unauthenticated-safe
list endpoint (``list_datasets``/``list_reports``), already gated the same way
the rest of the app gates it (``list_workflows`` needs a login), or purely
session-local (``state.chat_history``/``state.current_visualization``) —
nothing new is computed here that the backend doesn't already provide.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state
from frontend.utils import format_timestamp

_MAX_RECENT = 5


def _render_quick_actions(state: Any) -> None:
    st.subheader("Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("⬆️ Upload Data", width="stretch"):
            st.switch_page("pages/1_Upload.py")
    with col2:
        if st.button("📊 Run Analysis", width="stretch"):
            st.switch_page("pages/4_Analysis.py")
    with col3:
        if st.button("🤖 Ask Copilot", width="stretch"):
            st.switch_page("pages/9_Chat.py")
    with col4:
        if st.button("📑 Generate Report", width="stretch"):
            st.switch_page("pages/11_Reports.py")


def _render_ai_nudge(state: Any) -> None:
    analysis = state.current_analysis
    if analysis and analysis.get("insights"):
        top_insight = analysis["insights"][0]
        st.info(f"💡 **AI recommendation:** {top_insight.get('message', '')}")
    elif state.selected_dataset is None:
        st.info("💡 **AI recommendation:** Upload your first dataset to get started.")
    elif analysis is None:
        st.info(
            f"💡 **AI recommendation:** Run Analysis on '{state.selected_dataset['dataset_name']}' "
            "to see KPIs, trends, and insights."
        )


def _render_continue_cards(state: Any) -> None:
    cards = []
    if state.chat_history:
        last_question = next((m["content"] for m in reversed(state.chat_history) if m["role"] == "user"), None)
        if last_question:
            cards.append(("💬 Continue your conversation", last_question, "pages/9_Chat.py"))
    if state.current_visualization:
        cards.append(("📈 Continue exploring your dashboard", "Pick up where you left off.", "pages/5_Visualization.py"))

    if not cards:
        return
    st.subheader("Pick Up Where You Left Off")
    cols = st.columns(len(cards))
    for col, (title, caption, target) in zip(cols, cards, strict=True):
        with col, st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(caption[:120])
            if st.button("Continue", key=f"continue_{target}", width="stretch"):
                st.switch_page(target)


def _render_recent_datasets(state: Any, client: APIClient) -> None:
    st.subheader("Recent Datasets")
    try:
        datasets = client.list_datasets()
    except APIClientError:
        st.caption("Couldn't load datasets right now.")
        return
    if not datasets:
        st.caption("No datasets uploaded yet.")
        return

    recent = sorted(datasets, key=lambda d: d.get("loaded_at") or "", reverse=True)[:_MAX_RECENT]
    for dataset in recent:
        col1, col2 = st.columns([4, 1])
        col1.markdown(f"**{dataset['dataset_name']}** — {dataset['row_count']} rows · {format_timestamp(dataset.get('loaded_at'))}")
        if col2.button("Open", key=f"open_dataset_{dataset['dataset_id']}"):
            state.selected_dataset = dataset
            st.switch_page("pages/2_Datasets.py")


def _render_recent_reports(client: APIClient) -> None:
    st.subheader("Recent Reports")
    try:
        reports = client.list_reports()
    except APIClientError:
        st.caption("Couldn't load reports right now.")
        return
    if not reports:
        st.caption("No reports generated yet.")
        return
    for report in reports[:_MAX_RECENT]:
        st.markdown(f"- **{report['title']}** — {format_timestamp(report.get('generated_at'))}")
    if st.button("View all reports"):
        st.switch_page("pages/11_Reports.py")


def _render_recent_workflows(state: Any) -> None:
    st.subheader("Recent Workflows")
    if not state.is_authenticated:
        st.caption("Log in on the Settings page to see your workflows.")
        return
    client = APIClient(state.backend_url, access_token=state.access_token)
    try:
        workflows = client.list_workflows()
    except APIClientError:
        st.caption("Couldn't load workflows right now.")
        return
    if not workflows:
        st.caption("No workflows yet.")
        return
    for workflow in workflows[:_MAX_RECENT]:
        st.markdown(f"- **{workflow['definition']['name']}** — {workflow['status']}")
    if st.button("View all workflows"):
        st.switch_page("pages/23_Workflows.py")


def _render_system_status(state: Any, client: APIClient) -> None:
    try:
        client.health_check()
        st.caption("🟢 All systems operational")
    except APIClientError:
        st.caption("🔴 Backend unreachable — check Settings.")


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Dashboard",
    "Your workspace: pick up a recent dataset, report, or workflow, or start something new.",
    icon="🏠",
)

client = APIClient(state.backend_url)

_render_ai_nudge(state)
_render_quick_actions(state)
st.divider()
_render_continue_cards(state)

col1, col2, col3 = st.columns(3)
with col1:
    _render_recent_datasets(state, client)
with col2:
    _render_recent_reports(client)
with col3:
    _render_recent_workflows(state)

st.divider()
_render_system_status(state, client)
