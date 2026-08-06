"""Settings page: Profile (login/account), Appearance, AI Provider, Developer Mode,
and System Information — the one place account and preference controls live.

Every control here writes straight into ``DashboardState`` (backed by
``st.session_state``), so changes take effect immediately and are read by
every other page — there is nothing to separately "save". Profile absorbs
what used to be the Security page's own login form and current-user
display (Phase v1.0 navigation redesign) — Security itself now only holds
token/role/audit/user-management detail and moved behind Advanced Mode, but
a normal user still needs to log in from *somewhere* always-visible, so
that capability lives here instead.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state
from frontend.utils import format_timestamp

LAYOUT_TYPES = ["executive_summary", "detailed_analysis", "kpi_dashboard", "comparison_dashboard"]
_LAYOUT_LABELS = {
    "executive_summary": "Executive Summary", "detailed_analysis": "Detailed Analysis",
    "kpi_dashboard": "KPI Dashboard", "comparison_dashboard": "Comparison Dashboard",
}
THEMES = ["light", "dark", "corporate"]
CHART_DENSITIES = ["compact", "comfortable", "spacious"]


def _render_login_form(state: Any) -> None:
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In", type="primary")

    if submitted:
        client = APIClient(state.backend_url)
        try:
            result = client.login(username, password)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.set_authenticated_session(result["access_token"], result["refresh_token"], result["user"])
            state.add_activity(f"Logged in as '{result['user']['username']}'.")
            st.rerun()


def _render_profile(state: Any) -> None:
    st.subheader("Profile")
    if not state.is_authenticated:
        st.caption("Log in to save reports, run workflows, and access your account.")
        _render_login_form(state)
        return

    user = state.current_user
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**{user['full_name'] or user['username']}** (`{user['username']}`)")
        st.caption(f"{user['email']} — role: `{user['role']}`" + ("" if user["is_active"] else " — inactive"))
    with col2:
        if st.button("Log Out", type="secondary"):
            client = APIClient(state.backend_url)
            try:
                if state.refresh_token:
                    client.logout(state.refresh_token)
            except APIClientError:
                pass  # logging out locally must succeed even if the backend call fails
            state.clear_authenticated_session()
            state.add_activity(f"Logged out '{user['username']}'.")
            st.rerun()


def _render_appearance(state: Any) -> None:
    st.subheader("Appearance")
    previous_theme = state.theme
    st.selectbox("Theme", THEMES, key="dashboard_theme")
    if state.theme != previous_theme:
        state.add_activity(f"Changed theme to '{state.theme}'.")

    previous_layout = state.current_layout
    st.selectbox(
        "Default Layout", LAYOUT_TYPES, key="dashboard_current_layout",
        format_func=lambda value: _LAYOUT_LABELS.get(value, value),
    )
    if state.current_layout != previous_layout:
        state.add_activity(f"Changed default layout to '{_LAYOUT_LABELS.get(state.current_layout, state.current_layout)}'.")

    current_density = state.chart_density
    density_index = CHART_DENSITIES.index(current_density) if current_density in CHART_DENSITIES else 1
    new_density = st.selectbox("Chart Density", CHART_DENSITIES, index=density_index)
    if new_density != current_density:
        state.chart_density = new_density
        state.add_activity(f"Changed chart density to '{new_density}'.")


def _render_ai_provider(state: Any) -> None:
    st.subheader("AI Provider")
    client = APIClient(state.backend_url)
    try:
        status = client.get_system_status()
    except APIClientError as exc:
        render_api_error(exc)
        return

    ai_provider = status["ai_provider"]
    model_info = status["model_info"]
    col1, col2, col3 = st.columns(3)
    col1.metric("Provider", ai_provider["provider"])
    col2.metric("Status", "Available" if ai_provider["healthy"] else "Unavailable")
    col3.metric("Model", model_info["name"])
    st.caption(f"Last checked: {format_timestamp(ai_provider.get('checked_at'))}")


def _render_developer_mode(state: Any) -> None:
    st.subheader("Developer Mode")
    new_advanced_mode = st.toggle(
        "Advanced Mode", value=state.advanced_mode,
        help="Reveal engineering-oriented pages (Observability, Plugins, Distributed, Security, ...) in the sidebar.",
    )
    if new_advanced_mode != state.advanced_mode:
        state.advanced_mode = new_advanced_mode
        state.add_activity(f"{'Enabled' if new_advanced_mode else 'Disabled'} Advanced Mode.")
        st.rerun()  # the sidebar's own nav tree must rebuild against the new flag

    new_debug_mode = st.toggle("Debug Mode", value=state.debug_mode, help="Show raw JSON payloads on supported pages.")
    if new_debug_mode != state.debug_mode:
        state.debug_mode = new_debug_mode
        state.add_activity(f"{'Enabled' if new_debug_mode else 'Disabled'} debug mode.")


def _render_system_information(state: Any) -> None:
    st.subheader("System Information")
    client = APIClient(state.backend_url)
    try:
        status = client.get_system_status()
    except APIClientError as exc:
        render_api_error(exc)
        status = None

    if status is not None:
        col1, col2 = st.columns(2)
        col1.metric("Backend Health", status["health"]["status"].title())
        col2.metric("Application Version", status["application_version"])

    new_backend_url = st.text_input("Backend URL", value=state.backend_url)
    if new_backend_url != state.backend_url:
        if new_backend_url.startswith(("http://", "https://")):
            state.backend_url = new_backend_url
            state.add_activity(f"Changed backend URL to '{new_backend_url}'.")
            st.rerun()  # sidebar already rendered this run against the old URL; force a redraw
        else:
            st.error("Backend URL must start with http:// or https://")

    if state.debug_mode:
        st.divider()
        st.caption("Current preferences")
        st.json(state.preferences)


state = get_dashboard_state()
render_sidebar(state)
page_header("Settings", "Your profile, appearance preferences, AI provider status, and developer options.", icon="🔧")

_render_profile(state)
st.divider()
_render_appearance(state)
st.divider()
_render_ai_provider(state)
st.divider()
_render_developer_mode(state)
st.divider()
_render_system_information(state)
