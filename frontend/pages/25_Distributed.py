"""Distributed page: the Distributed Execution & Horizontal Scaling layer's
own dashboard — registered workers, live worker status, cluster health,
queue depth, worker capabilities, task assignments, lease status, and
heartbeat freshness.

Requires authentication (Phase 35) — every ``/api/v1/distributed/*``
endpoint is permission-gated, same as every other protected router.
"""

from datetime import UTC, datetime
from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state

_STATUS_ICONS = {"online": "🟢", "busy": "🟡", "offline": "⚫", "failed": "🔴", "draining": "🟠"}


def _status_label(status: str) -> str:
    return f"{_STATUS_ICONS.get(status, '')} {status}"


def _authenticated_client(state: Any) -> APIClient:
    return APIClient(state.backend_url, access_token=state.access_token)


def _heartbeat_age_seconds(last_heartbeat: str | None) -> float | None:
    if not last_heartbeat:
        return None
    return (datetime.now(UTC) - datetime.fromisoformat(last_heartbeat)).total_seconds()


def _render_cluster_health(client: APIClient) -> None:
    st.subheader("Cluster Health")
    try:
        stats = client.get_cluster_statistics()
    except APIClientError as exc:
        render_api_error(exc)
        return
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Workers", stats["total_workers"])
    col2.metric("Online", stats["online_workers"])
    col3.metric("Busy", stats["busy_workers"])
    col4.metric("Offline/Failed", stats["offline_workers"] + stats["failed_workers"])
    col5.metric("Draining", stats["draining_workers"])
    col1, col2, col3 = st.columns(3)
    col1.metric("Active tasks", f"{stats['total_active_tasks']} / {stats['total_capacity']}")
    col2.metric("Queue depth", stats["queue_depth"])
    col3.metric("Retry queue depth", stats["retry_queue_depth"])


def _render_register_form(state: Any, client: APIClient) -> None:
    with st.expander("Register a worker"):
        with st.form("register_worker"):
            worker_id = st.text_input("Worker ID")
            hostname = st.text_input("Hostname", value="localhost")
            capabilities = st.multiselect(
                "Capabilities (node names)",
                options=["file_agent", "sql_agent", "browser_agent", "report_agent", "executive_summary_agent"],
            )
            max_parallel = st.number_input("Maximum parallel tasks", min_value=1, value=1, step=1)
            submitted = st.form_submit_button("Register", type="primary")
        if submitted and worker_id:
            try:
                worker = client.register_worker(worker_id, hostname, capabilities, int(max_parallel))
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.add_activity(f"Registered worker '{worker['worker_id']}'.")
                st.rerun()


def _render_workers_table(state: Any, client: APIClient) -> list[dict[str, Any]]:
    st.subheader("Registered Workers")
    try:
        workers = client.list_workers()
    except APIClientError as exc:
        render_api_error(exc)
        return []

    if not workers:
        st.info("No workers registered yet — every step still runs in-process, exactly as before this phase.")
        return []

    st.dataframe(
        [
            {
                "Worker": w["worker_id"],
                "Host": w["hostname"],
                "Status": _status_label(w["status"]),
                "Capabilities": ", ".join(c["node_name"] for c in w["capabilities"]) or "—",
                "Load": f"{len(w['active_tasks'])}/{w['maximum_parallel_tasks']}",
                "Heartbeat age (s)": (
                    f"{age:.1f}" if (age := _heartbeat_age_seconds(w['last_heartbeat'])) is not None else "—"
                ),
            }
            for w in workers
        ],
        width="stretch", hide_index=True,
    )

    for worker in workers:
        col1, col2, col3 = st.columns(3)
        if col1.button("Heartbeat", key=f"hb_{worker['worker_id']}"):
            try:
                client.send_worker_heartbeat(worker["worker_id"])
            except APIClientError as exc:
                render_api_error(exc)
            else:
                st.rerun()
        if col2.button("Drain", key=f"drain_{worker['worker_id']}"):
            try:
                client.drain_worker(worker["worker_id"])
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.add_activity(f"Draining worker '{worker['worker_id']}'.")
                st.rerun()
        if col3.button("Shutdown", key=f"shutdown_{worker['worker_id']}"):
            try:
                client.shutdown_worker(worker["worker_id"])
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.add_activity(f"Shut down worker '{worker['worker_id']}'.")
                st.rerun()

    return workers


def _render_queue(client: APIClient) -> None:
    st.subheader("Task Queue")
    try:
        snapshot = client.get_queue_snapshot()
    except APIClientError as exc:
        render_api_error(exc)
        return

    tab_active, tab_retry = st.tabs([f"Active ({len(snapshot['active'])})", f"Retry ({len(snapshot['retry'])})"])
    with tab_active:
        if snapshot["active"]:
            st.dataframe(
                [
                    {
                        "Assignment": a["assignment_id"], "Step": a["step_id"], "Agent": a["node_name"],
                        "Worker": a["worker_id"], "Lease": a["lease_id"], "Status": a["status"],
                    }
                    for a in snapshot["active"]
                ],
                width="stretch", hide_index=True,
            )
        else:
            st.caption("No active task assignments.")
    with tab_retry:
        if snapshot["retry"]:
            st.dataframe(
                [
                    {
                        "Assignment": a["assignment_id"], "Step": a["step_id"], "Agent": a["node_name"],
                        "Retries": a["retry_count"], "Status": a["status"],
                    }
                    for a in snapshot["retry"]
                ],
                width="stretch", hide_index=True,
            )
        else:
            st.caption("No tasks awaiting retry.")


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Distributed",
    "Distributed Execution & Horizontal Scaling — register workers, monitor cluster health, "
    "and inspect dispatch/lease/recovery state. Workers are real, tracked capacity — the step "
    "itself still runs in-process through the same real agent service.",
)

if not state.is_authenticated:
    st.info("Log in on the **Settings** page first — every distributed endpoint requires authentication.")
else:
    client = _authenticated_client(state)
    _render_cluster_health(client)
    st.divider()
    _render_register_form(state, client)
    _render_workers_table(state, client)
    st.divider()
    _render_queue(client)
