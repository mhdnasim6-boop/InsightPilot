"""Operations page: current profile, feature flags, health, diagnostics,
loaded plugins, memory usage, and the full environment report.

Stateless, like Plugins (Phase 33): everything here reads the backend's
own live operational state on every rerun — there is no "current
selection" concept worth tracking in session state.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state

_SEVERITY_ICONS = {"error": "🔴", "warning": "🟡", "info": "⚪"}


def _render_health(client: APIClient) -> None:
    st.subheader("Health")
    col1, col2 = st.columns(2)

    with col1:
        try:
            liveness = client.get_operations_health()
        except APIClientError as exc:
            render_api_error(exc)
        else:
            st.metric("Liveness", "🟢 Alive" if liveness["alive"] else "🔴 Down")
            st.caption(f"{liveness['application']} v{liveness['version']}")

    with col2:
        try:
            readiness = client.get_operations_readiness()
        except APIClientError as exc:
            render_api_error(exc)
        else:
            st.metric("Readiness", "🟢 Ready" if readiness["ready"] else "🔴 Not ready")
            st.caption(f"Profile: {readiness['profile']}")
            with st.expander("Startup stages"):
                for stage in readiness["stages"]:
                    icon = "✅" if stage["status"] == "completed" else "❌"
                    st.markdown(f"{icon} **{stage['name']}** — {stage['duration_ms']:.2f}ms")
                    if stage["error"]:
                        st.error(stage["error"])


def _render_configuration(client: APIClient) -> None:
    st.subheader("Configuration")
    try:
        config = client.get_operations_configuration()
    except APIClientError as exc:
        render_api_error(exc)
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Profile", config["profile"])
    col2.metric("Environment", config["environment"])
    col3.metric("App version", config["application_version"])

    st.caption(f"Log level: `{config['log_level']}` — AI provider: `{config['ai_default_provider']}`")

    st.markdown("**Directories**")
    st.dataframe(
        [
            {
                "Path": d["path"],
                "Label": d["label"],
                "Exists": "✅" if d["exists"] else "—",
                "Is directory": "✅" if d["is_directory"] else ("❌" if d["is_directory"] is False else "—"),
            }
            for d in config["directories"]
        ],
        width="stretch",
        hide_index=True,
    )

    validation = config["validation"]
    st.markdown(f"**Validation** — {'✅ Valid' if validation['is_valid'] else '❌ Invalid'}")
    for issue in validation["issues"]:
        icon = _SEVERITY_ICONS.get(issue["severity"], "")
        st.caption(f"{icon} [{issue['area']}] {issue['message']}")


def _render_feature_flags(client: APIClient) -> None:
    st.subheader("Feature Flags")
    try:
        flags = client.get_feature_flags()
    except APIClientError as exc:
        render_api_error(exc)
        return
    st.dataframe(
        [
            {"Flag": f["name"], "Enabled": "✅" if f["enabled"] else "—", "Description": f["description"]}
            for f in flags
        ],
        width="stretch",
        hide_index=True,
    )


def _render_diagnostics(client: APIClient) -> None:
    st.subheader("Diagnostics")
    try:
        diagnostics = client.get_operations_diagnostics()
    except APIClientError as exc:
        render_api_error(exc)
        return

    dep = diagnostics["dependency_report"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Loaded plugins", len(dep["loaded_plugins"]))
    col2.metric("Failed plugins", len(dep["failed_plugins"]))
    col3.metric("Registered tools", len(dep["registered_tools"]))
    col4.metric("Registered agents", len(dep["registered_agents"]))

    with st.expander("Loaded plugins"):
        st.write(dep["loaded_plugins"] or "None")
    with st.expander("Failed plugins"):
        st.write(dep["failed_plugins"] or "None")
    with st.expander("Registered tools"):
        st.write(dep["registered_tools"])
    with st.expander("Registered agents"):
        st.write(dep["registered_agents"])

    st.markdown("**Memory usage**")
    memory: dict[str, Any] = diagnostics["memory_statistics"]
    col1, col2, col3 = st.columns(3)
    col1.metric("Total items", memory["total_items"])
    col2.metric("Recent activity", memory["recent_activity_count"])
    col3.metric("Avg. importance", f"{memory['average_importance']:.2f}")
    if memory["by_type"]:
        st.caption("By type: " + ", ".join(f"{k}={v}" for k, v in memory["by_type"].items()))


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Operations",
    "Configuration profile, feature flags, health, diagnostics, loaded plugins, and memory usage.",
)

client = APIClient(state.backend_url)

_render_health(client)
st.divider()
_render_configuration(client)
st.divider()
_render_feature_flags(client)
st.divider()
_render_diagnostics(client)
