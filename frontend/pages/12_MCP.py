"""MCP page: registered servers, their capabilities, transport, and health.

Registration only — no connection, tool-listing, or invocation controls
exist yet, since no real MCPClient implementation exists anywhere in this
phase. Registering a server here only records its metadata; it never
attempts to reach it, and its status stays "disconnected" until a future
phase adds real connectivity.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state

_TRANSPORTS = ["stdio", "http", "websocket"]
_STATUS_ICONS = {
    "connected": "🟢",
    "starting": "🟡",
    "stopping": "🟡",
    "disconnected": "⚪",
    "failed": "🔴",
}
_STATUS_ORDER = ["connected", "starting", "stopping", "disconnected", "failed"]


def _render_health_summary(client: APIClient) -> None:
    st.subheader("Health")
    try:
        summary = client.get_mcp_health()
    except APIClientError as exc:
        render_api_error(exc)
        return

    cols = st.columns(len(_STATUS_ORDER))
    for col, status in zip(cols, _STATUS_ORDER, strict=False):
        col.metric(f"{_STATUS_ICONS[status]} {status.capitalize()}", summary["by_status"].get(status, 0))
    st.caption(f"Total registered servers: {summary['total_servers']}")


def _render_registration_form(client: APIClient, state: Any) -> None:
    st.subheader("Register a Server")
    try:
        capability_options = client.list_mcp_capabilities()
    except APIClientError as exc:
        render_api_error(exc)
        capability_options = []

    with st.form("mcp_register_form"):
        col1, col2 = st.columns(2)
        server_id = col1.text_input("Server ID", placeholder="filesystem-local")
        name = col2.text_input("Name", placeholder="Local Filesystem")
        description = st.text_input("Description (optional)")
        col3, col4 = st.columns(2)
        transport = col3.selectbox("Transport", _TRANSPORTS)
        capabilities = col4.multiselect("Capabilities", capability_options)
        submitted = st.form_submit_button("Register", type="primary")

    if not submitted:
        return
    if not server_id or not name:
        st.warning("Server ID and Name are required.")
        return

    try:
        client.register_mcp_server(
            server_id=server_id,
            name=name,
            transport=transport,
            description=description or None,
            capabilities=capabilities,
        )
    except APIClientError as exc:
        render_api_error(exc)
        return

    state.add_activity(f"Registered MCP server '{server_id}'.")
    st.success(f"Server '{server_id}' registered.")


def _render_servers_table(client: APIClient, state: Any) -> None:
    st.subheader("Registered Servers")
    try:
        servers = client.list_mcp_servers()
    except APIClientError as exc:
        render_api_error(exc)
        return

    if not servers:
        st.info("No MCP servers registered yet. Register one above.")
        return

    st.dataframe(
        [
            {
                "Status": f"{_STATUS_ICONS.get(s['status'], '')} {s['status']}",
                "Server ID": s["server_id"],
                "Name": s["name"],
                "Description": s.get("description") or "—",
                "Transport": s["transport"],
                "Capabilities": ", ".join(s["capabilities"]) or "—",
                "Version": s["version"],
            }
            for s in servers
        ],
        width="stretch",
        hide_index=True,
    )

    server_ids = [s["server_id"] for s in servers]
    to_remove = st.selectbox("Remove a server", server_ids)
    if st.button("Remove Selected Server"):
        try:
            client.remove_mcp_server(to_remove)
        except APIClientError as exc:
            render_api_error(exc)
            return
        state.add_activity(f"Removed MCP server '{to_remove}'.")
        st.success(f"Server '{to_remove}' removed.")


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "MCP Servers",
    "Registered MCP servers, their capabilities, transport, and health. No connection controls yet.",
)

client = APIClient(state.backend_url)

# Registration/removal (both mutating) run before the health summary is
# fetched, so a server registered or removed on this same rerun is
# already reflected in the counts below — not stale by one rerun.
_render_registration_form(client, state)
st.divider()
_render_servers_table(client, state)
st.divider()
_render_health_summary(client)
