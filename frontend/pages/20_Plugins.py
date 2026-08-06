"""Plugins page: installed plugins, their lifecycle state, what they
contributed, and Load/Unload/Reload controls.

Stateless by design (unlike Execution/Collaboration/Reflection/Adaptive):
the plugin registry is process-wide, shared, and cheap to re-fetch, so
this page always shows the live ``PluginRegistry`` state on every rerun
rather than tracking a "current" selection in session state.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state

_STATE_ICONS = {
    "discovered": "⚪",
    "validated": "🔵",
    "loaded": "🔵",
    "initialized": "🔵",
    "registered": "🟢",
    "failed": "🔴",
    "unloaded": "⚫",
}


def _state_label(state: str) -> str:
    return f"{_STATE_ICONS.get(state, '')} {state}"


def _render_controls(client: APIClient, state: Any) -> None:
    st.subheader("Discover & Reload")
    col1, col2 = st.columns(2)
    if col1.button("Load new plugins", type="primary"):
        try:
            client.load_plugins()
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.add_activity("Loaded any newly-discovered plugins.")
            st.rerun()
    if col2.button("Reload all plugins"):
        try:
            client.reload_plugins()
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.add_activity("Reloaded every plugin.")
            st.rerun()


def _render_plugin_table(plugins: list[dict[str, Any]]) -> None:
    st.subheader("Installed Plugins")
    if not plugins:
        st.info("No plugins discovered yet.")
        return
    st.dataframe(
        [
            {
                "ID": p["manifest"]["metadata"]["id"],
                "Name": p["manifest"]["metadata"]["name"],
                "Version": p["manifest"]["metadata"]["version"],
                "Author": p["manifest"]["metadata"]["author"],
                "Status": _state_label(p["state"]),
                "Provides": ", ".join(p["manifest"]["provides"]) or "—",
                "Extensions": len(p["extensions"]),
            }
            for p in plugins
        ],
        width="stretch",
        hide_index=True,
    )


def _render_plugin_details(plugins: list[dict[str, Any]], client: APIClient, state: Any) -> None:
    if not plugins:
        return
    st.subheader("Plugin Details")
    options = {f"{p['manifest']['metadata']['name']} ({p['manifest']['metadata']['id']})": p["manifest"]["metadata"]["id"] for p in plugins}
    chosen_label = st.selectbox("Select a plugin", list(options.keys()))
    plugin_id = options[chosen_label]

    try:
        plugin = client.get_plugin(plugin_id)
    except APIClientError as exc:
        render_api_error(exc)
        return

    metadata = plugin["manifest"]["metadata"]
    with st.container(border=True):
        st.markdown(f"**{metadata['name']}** — v{metadata['version']} by {metadata['author']}")
        st.caption(metadata["description"])
        st.markdown(f"Status: {_state_label(plugin['state'])}")
        st.caption(f"Source: `{plugin['source_path']}`")
        st.caption(f"Compatible InsightPilot version: {plugin['manifest']['compatible_version']}")
        if metadata["tags"]:
            st.caption("Tags: " + ", ".join(metadata["tags"]))

        if plugin["extensions"]:
            st.markdown("**Extensions contributed:**")
            for extension in plugin["extensions"]:
                st.markdown(f"- `{extension['kind']}`: {extension['name']}")
        else:
            st.caption("No extensions registered.")

        if plugin["error"]:
            st.error(f"Failure reason: {plugin['error']}")

        col1, col2 = st.columns(2)
        if col1.button("Reload this plugin", key=f"reload_{plugin_id}"):
            try:
                client.reload_plugins(plugin_id)
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.add_activity(f"Reloaded plugin '{plugin_id}'.")
                st.rerun()
        if col2.button("Unload this plugin", key=f"unload_{plugin_id}", disabled=plugin["state"] not in {"registered", "initialized", "loaded"}):
            try:
                client.unload_plugin(plugin_id)
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.add_activity(f"Unloaded plugin '{plugin_id}'.")
                st.rerun()


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Plugins",
    "Third-party extensions — Agents, Tools, Exporters, Visualizations, AI Providers, "
    "Memory Providers, Approval Policies, Analyzers, and Optimizers — loaded from backend/extensions/.",
)

client = APIClient(state.backend_url)

_render_controls(client, state)
st.divider()

try:
    plugins = client.list_plugins()
except APIClientError as exc:
    render_api_error(exc)
    plugins = []

_render_plugin_table(plugins)
st.divider()
_render_plugin_details(plugins, client, state)
