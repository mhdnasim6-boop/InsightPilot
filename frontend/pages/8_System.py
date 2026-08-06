"""System page: backend health, AI provider, orchestration graph, and application version."""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state
from frontend.utils import format_timestamp

state = get_dashboard_state()
render_sidebar(state)
page_header("System", "Backend health, AI provider, orchestration graph, and application version.")

client = APIClient(state.backend_url)

if st.button("Refresh"):
    st.rerun()

status: dict[str, Any] | None
try:
    status = client.get_system_status()
except APIClientError as exc:
    render_api_error(exc)
    status = None

if status is not None:
    health = status["health"]
    ai_provider = status["ai_provider"]
    model_info = status["model_info"]
    graph = status["graph_metadata"]

    st.subheader("Overview")
    col1, col2, col3 = st.columns(3)
    col1.metric("Health", health["status"].title())
    col2.metric("AI Provider", "Available" if ai_provider["healthy"] else "Unavailable")
    col3.metric("Application Version", status["application_version"])

    st.subheader("Service Availability")
    availability_rows = [
        {"Service": "Backend API", "Status": health["status"], "Detail": health["application"]},
        {
            "Service": f"AI Provider ({ai_provider['provider']})",
            "Status": "healthy" if ai_provider["healthy"] else "unhealthy",
            "Detail": ai_provider.get("message") or "—",
        },
    ]
    st.dataframe(availability_rows, width="stretch", hide_index=True)
    st.caption(f"AI provider last checked: {format_timestamp(ai_provider.get('checked_at'))}")

    st.subheader("Current Model")
    col4, col5, col6 = st.columns(3)
    col4.metric("Model", model_info["name"])
    col5.metric("Max Input Tokens", model_info.get("max_input_tokens") or "—")
    col6.metric("Max Output Tokens", model_info.get("max_output_tokens") or "—")
    st.caption(f"Streaming supported: {'yes' if model_info.get('supports_streaming') else 'no'}")

    st.subheader("Orchestration Graph")
    st.caption(f"Entry point: `{graph.get('entry_point') or '—'}`")
    st.dataframe(
        [{"Node": node["name"], "Details": node.get("details") or {}} for node in graph.get("nodes", [])],
        width="stretch",
        hide_index=True,
    )
    if graph.get("edges"):
        st.dataframe(
            [{"From": edge["source"], "To": edge["target"]} for edge in graph["edges"]],
            width="stretch",
            hide_index=True,
        )

    if state.debug_mode:
        st.divider()
        st.subheader("Raw System Status")
        st.json(status)
