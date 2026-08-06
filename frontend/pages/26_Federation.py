"""Federation page: the Federated Multi-Cluster Orchestration layer's own
dashboard — registered clusters, cluster health, routing decisions,
cluster capabilities, global capacity, cluster topology, and failover
status.

Requires authentication (Phase 35) — every ``/api/v1/federation/*``
endpoint is permission-gated, same as every other protected router.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state

_STATUS_ICONS = {"online": "🟢", "degraded": "🟡", "offline": "⚫", "maintenance": "🟠", "failed": "🔴"}


def _status_label(status: str) -> str:
    return f"{_STATUS_ICONS.get(status, '')} {status}"


def _authenticated_client(state: Any) -> APIClient:
    return APIClient(state.backend_url, access_token=state.access_token)


def _render_global_capacity(client: APIClient) -> None:
    st.subheader("Global Capacity")
    try:
        stats = client.get_federation_statistics()
    except APIClientError as exc:
        render_api_error(exc)
        return
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Clusters", stats["total_clusters"])
    col2.metric("Online", stats["online_clusters"])
    col3.metric("Degraded", stats["degraded_clusters"])
    col4.metric("Offline/Failed", stats["offline_clusters"] + stats["failed_clusters"])
    col5.metric("Maintenance", stats["maintenance_clusters"])
    col1, col2, col3 = st.columns(3)
    col1.metric("Active remote executions", f"{stats['active_remote_executions']} / {stats['total_capacity']}")
    col2.metric("Registered workers (fleet)", stats["total_registered_workers"])
    col3.metric("Pending routing decisions", stats["pending_routing_decisions"])


def _render_register_form(state: Any, client: APIClient) -> None:
    with st.expander("Register a remote cluster"):
        with st.form("register_cluster"):
            cluster_id = st.text_input("Cluster ID")
            name = st.text_input("Name")
            endpoint = st.text_input("Endpoint", placeholder="https://cluster-2.example.com")
            capabilities = st.multiselect(
                "Supported agents",
                options=["file_agent", "sql_agent", "browser_agent", "report_agent", "executive_summary_agent"],
            )
            max_concurrent = st.number_input("Maximum concurrent executions", min_value=1, value=1, step=1)
            submitted = st.form_submit_button("Register", type="primary")
        if submitted and cluster_id and name and endpoint:
            try:
                cluster = client.register_cluster(
                    cluster_id, name, endpoint,
                    {"supported_agents": capabilities, "maximum_concurrent_executions": int(max_concurrent)},
                )
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.add_activity(f"Registered cluster '{cluster['cluster_id']}'.")
                st.rerun()


def _render_clusters_table(state: Any, client: APIClient) -> list[dict[str, Any]]:
    st.subheader("Registered Clusters")
    try:
        clusters = client.list_clusters()
    except APIClientError as exc:
        render_api_error(exc)
        return []

    st.dataframe(
        [
            {
                "Cluster": c["cluster_id"], "Name": c["name"], "Local": "✅" if c["is_local"] else "",
                "Status": _status_label(c["status"]), "Health": f"{c['health_score']:.2f}",
                "Agents": ", ".join(c["capabilities"]["supported_agents"]) or "—",
                "Plugins": ", ".join(c["capabilities"]["supported_plugins"]) or "—",
                "Load": f"{len(c['active_remote_executions'])}/{c['capabilities']['maximum_concurrent_executions']}",
                "Workers": c["registered_workers"],
            }
            for c in clusters
        ],
        width="stretch", hide_index=True,
    )

    for cluster in clusters:
        if cluster["is_local"]:
            continue
        if st.button("Remove", key=f"remove_{cluster['cluster_id']}"):
            try:
                client.remove_cluster(cluster["cluster_id"])
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.add_activity(f"Removed cluster '{cluster['cluster_id']}'.")
                st.rerun()

    return clusters


def _render_topology(clusters: list[dict[str, Any]], routing_decisions: list[dict[str, Any]]) -> None:
    st.subheader("Cluster Topology")
    lines = ["flowchart LR"]
    for cluster in clusters:
        icon = _STATUS_ICONS.get(cluster["status"], "")
        label = "local" if cluster["is_local"] else cluster["name"]
        capacity = f"{len(cluster['active_remote_executions'])}/{cluster['capabilities']['maximum_concurrent_executions']}"
        lines.append(f'    {cluster["cluster_id"]}["{icon} {label}<br/>{capacity}"]')
    for decision in routing_decisions[-20:]:
        lines.append(f'    {decision["selected_cluster_id"]} -->|{decision["status"]}| {decision["workflow_id"]}')
    st.code("\n".join(lines), language="mermaid")


def _render_routing_and_failover(client: APIClient) -> list[dict[str, Any]]:
    st.subheader("Routing Decisions & Failover")
    try:
        decisions = client.get_routing_decisions()
    except APIClientError as exc:
        render_api_error(exc)
        return []

    rerouted = [d for d in decisions if d["reroute_count"] > 0]
    if rerouted:
        st.warning(f"{len(rerouted)} routing decision(s) were rerouted due to an unavailable cluster.")

    if decisions:
        st.dataframe(
            [
                {
                    "Workflow": d["workflow_id"][:12], "Cluster": d["selected_cluster_id"], "Status": d["status"],
                    "Reroutes": d["reroute_count"], "Reason": d["reason"],
                }
                for d in reversed(decisions[-50:])
            ],
            width="stretch", hide_index=True,
        )
    else:
        st.caption("No routing decisions yet.")
    return decisions


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Federation",
    "Federated Multi-Cluster Orchestration — register remote clusters, monitor global "
    "health/capacity, and inspect routing/failover decisions. A workload's real execution "
    "always still runs in-process locally; a routing decision only records which cluster "
    "is credited with it (no networking/RPC in this phase).",
)

if not state.is_authenticated:
    st.info("Log in on the **Settings** page first — every federation endpoint requires authentication.")
else:
    client = _authenticated_client(state)
    _render_global_capacity(client)
    st.divider()
    _render_register_form(state, client)
    clusters = _render_clusters_table(state, client)
    st.divider()
    decisions = _render_routing_and_failover(client)
    st.divider()
    _render_topology(clusters, decisions)
