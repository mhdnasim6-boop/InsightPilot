"""Security page: token information, role/permission viewers, audit log viewer,
and (permission-permitting) user management — the deeper administrative detail
behind Advanced Mode.

Logging in/out and viewing your own profile live on the Settings page now
(Phase v1.0 navigation redesign) — that capability must always be reachable
even with Advanced Mode off, so it can't live only here. This page assumes a
session already exists and only adds admin-oriented depth on top of it.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError, APIError
from frontend.components import render_api_error, render_empty_state
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state


def _authenticated_client(state: Any) -> APIClient:
    return APIClient(state.backend_url, access_token=state.access_token)


def _render_token_info(state: Any) -> None:
    st.subheader("Token Information")
    access = state.access_token or ""
    refresh = state.refresh_token or ""
    col1, col2 = st.columns(2)
    col1.metric("Access token", f"{access[:12]}…{access[-6:]}" if len(access) > 18 else access)
    col2.metric("Refresh token", f"{refresh[:12]}…{refresh[-6:]}" if len(refresh) > 18 else refresh)
    if st.button("Refresh Token Pair"):
        client = APIClient(state.backend_url)
        try:
            result = client.refresh_token(state.refresh_token)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.set_authenticated_session(result["access_token"], result["refresh_token"], result["user"])
            state.add_activity("Refreshed access/refresh token pair.")
            st.rerun()


def _render_roles_and_permissions(state: Any) -> None:
    st.subheader("Roles & Permissions")
    client = _authenticated_client(state)
    try:
        roles = client.get_roles()
        permissions = client.get_permissions()
    except APIClientError as exc:
        render_api_error(exc)
        return

    my_role = state.current_user["role"]
    my_permissions = set(roles.get(my_role, []))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Your permissions**")
        for permission in permissions:
            st.markdown(f"{'✅' if permission in my_permissions else '⬜'} `{permission}`")
    with col2:
        st.markdown("**Roles catalog**")
        st.dataframe(
            [{"Role": role, "Permissions": ", ".join(perms)} for role, perms in roles.items()],
            width="stretch", hide_index=True,
        )


def _render_audit_log(state: Any) -> None:
    st.subheader("Audit Log")
    client = _authenticated_client(state)
    try:
        events = client.get_audit_log(limit=50)
    except APIError as exc:
        if exc.status_code == 403:
            st.info("Your role doesn't include audit-log visibility (requires `view_audit`).")
        else:
            render_api_error(exc)
        return
    except APIClientError as exc:
        render_api_error(exc)
        return

    if not events:
        st.caption("No audit events recorded yet.")
        return
    st.dataframe(
        [
            {
                "Time": e["timestamp"][:19], "User": e["username"], "Method": e["method"],
                "Endpoint": e["endpoint"], "Status": e["status_code"], "Success": "✅" if e["success"] else "❌",
                "Duration (ms)": round(e["duration_ms"], 1), "Request ID": e["request_id"][:8],
            }
            for e in events
        ],
        width="stretch", hide_index=True,
    )


def _render_user_management(state: Any) -> None:
    st.subheader("User Management")
    client = _authenticated_client(state)
    try:
        users = client.list_security_users()
    except APIError as exc:
        if exc.status_code == 403:
            st.info("Your role doesn't include user management (requires `manage_users`).")
        else:
            render_api_error(exc)
        return
    except APIClientError as exc:
        render_api_error(exc)
        return

    st.dataframe(
        [
            {"Username": u["username"], "Email": u["email"], "Role": u["role"], "Active": "✅" if u["is_active"] else "❌"}
            for u in users
        ],
        width="stretch", hide_index=True,
    )

    with st.expander("Create a new user"):
        with st.form("create_user_form"):
            username = st.text_input("Username", key="new_user_username")
            email = st.text_input("Email", key="new_user_email")
            full_name = st.text_input("Full name", key="new_user_full_name")
            password = st.text_input("Password", type="password", key="new_user_password")
            role = st.selectbox("Role", ["viewer", "analyst", "operator", "developer", "admin", "plugin"])
            submitted = st.form_submit_button("Create User", type="primary")
        if submitted:
            try:
                client.create_security_user(username, email, password, role, full_name)
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.add_activity(f"Created user '{username}'.")
                st.rerun()


state = get_dashboard_state()
render_sidebar(state)
page_header("Security", "Token information, roles/permissions, audit log, and user management.", icon="🔐")

if not state.is_authenticated:
    clicked = render_empty_state(
        "You're not logged in",
        "Log in on the Settings page first, then come back here for token/role/audit detail.",
        icon="🔐", action_label="Go to Settings", key="security_go_to_settings",
    )
    if clicked:
        st.switch_page("pages/7_Settings.py")
else:
    _render_token_info(state)
    st.divider()
    _render_roles_and_permissions(state)
    st.divider()
    _render_audit_log(state)
    st.divider()
    _render_user_management(state)
