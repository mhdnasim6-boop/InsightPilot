"""Execution page: watch a run's live progress, per-step status, artifacts, and
pending approvals — regardless of whether it was started as a quick Draft-a-Plan
run or a Workflow run from the Planning page.

Both paths converge on the same ``state.current_dag_execution`` slot: a Draft-a-Plan
run starts one directly here; a Workflow run (Planning page's "My Workflows" tab)
bridges its own ``execution_id`` into this same slot right after starting, since
``WorkflowExecution.execution_id`` *is* the real underlying ``ExecutionService`` run
— so this page never needs to know which path a run came from, only which
``execution_id`` to poll (``backend.workflows.services.workflow_service`` always
executes through the exact same dependency-aware, parallel DAG engine).
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state

_STATUS_ICONS = {
    "pending": "⚪",
    "queued": "🔵",
    "running": "🟡",
    "completed": "🟢",
    "failed": "🔴",
    "paused": "🟠",
    "cancelled": "⚫",
}


def _status_label(status: str) -> str:
    return f"{_STATUS_ICONS.get(status, '')} {status}"


def _render_start_controls(state: Any, client: APIClient) -> None:
    st.subheader("Start a Run")
    if state.current_plan is None and state.current_workflow is None:
        st.info(
            "Nothing to run yet — draft a plan or build a workflow on the **Planning** page first, "
            "then come back here to watch it run."
        )
        return

    if state.current_plan is not None:
        plan = state.current_plan["execution_plan"]
        st.caption(f"Ready to run: **{plan.get('goal') or plan['plan_id']}** ({len(plan['steps'])} step(s))")
        if st.button("Run as parallel workflow", type="primary"):
            try:
                execution = client.start_execution({**plan, "status": "ready"}, session_id=state.session_id)
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.current_dag_execution = execution
                state.add_activity(f"Started a run for plan {plan['plan_id']}.")
                st.rerun()
    elif state.current_workflow is not None:
        st.caption(
            f"'{state.current_workflow['definition']['name']}' is ready — use **Run** on the "
            "Planning page's My Workflows tab to start it; progress then shows up here automatically."
        )


def _render_progress(execution: dict[str, Any], client: APIClient, state: Any) -> None:
    execution_id = execution["execution_id"]
    try:
        progress = client.get_execution_progress(execution_id)
    except APIClientError as exc:
        render_api_error(exc)
        return

    st.subheader("Progress")
    st.progress(progress["progress_percent"] / 100)
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Completed", len(progress["completed"]))
    col2.metric("Running", len(progress["running"]))
    col3.metric("Queued", len(progress["queued"]))
    col4.metric("Pending", len(progress["pending"]))
    col5.metric("Paused", len(progress["paused"]))
    col6.metric("Failed", len(progress["failed"]))

    status = execution["status"]
    status_renderer = {"completed": st.success, "failed": st.error, "cancelled": st.error, "paused": st.warning}
    status_renderer.get(status, st.info)(f"Run `{execution_id[:8]}` — status: **{status}**")
    st.caption(f"Last updated: {execution['updated_at']}")

    if st.button("Refresh"):
        try:
            state.current_dag_execution = client.get_execution(execution_id)
        except APIClientError as exc:
            render_api_error(exc)
        st.rerun()


def _render_nodes(execution: dict[str, Any]) -> None:
    st.subheader("Steps")
    rows = [
        {
            "Step": step_id,
            "Node": node["node_name"],
            "Status": _status_label(node["status"]),
            "Attempts": node["attempts"],
            "Error": node.get("error") or "—",
        }
        for step_id, node in execution["steps"].items()
    ]
    st.dataframe(rows, width="stretch", hide_index=True)


def _render_artifacts(execution: dict[str, Any]) -> None:
    with st.expander("Artifacts (per-step results)"):
        for step_id, node in execution["steps"].items():
            if node.get("result") is None:
                continue
            st.markdown(f"**{step_id}** (`{node['node_name']}`)")
            st.json(node["result"], expanded=False)


def _render_approval_and_controls(execution: dict[str, Any], client: APIClient, state: Any) -> None:
    execution_id = execution["execution_id"]
    plan_id = execution["plan_id"]

    if execution["status"] == "paused":
        try:
            pending = [a for a in client.list_approvals_for_plan(plan_id) if a["status"] == "pending"]
        except APIClientError as exc:
            render_api_error(exc)
            pending = []

        if pending:
            approver = st.text_input("Your name (optional)", key="dag_approver_name")
        for approval in pending:
            node_name = approval["metadata"].get("node_name", "unknown step")
            with st.container(border=True):
                st.markdown(f"Waiting for approval before **{node_name}** runs.")
                if approval.get("reason"):
                    st.caption(approval["reason"])
                col1, col2 = st.columns(2)
                if col1.button("Approve", key=f"dag_approve_{approval['approval_id']}", type="primary"):
                    try:
                        client.approve_approval(approval["approval_id"], approver=approver or None)
                    except APIClientError as exc:
                        render_api_error(exc)
                    else:
                        state.add_activity(f"Approved '{node_name}' for run {execution_id[:8]}.")
                        st.rerun()
                if col2.button("Reject", key=f"dag_reject_{approval['approval_id']}"):
                    try:
                        client.reject_approval(approval["approval_id"], approver=approver or None)
                    except APIClientError as exc:
                        render_api_error(exc)
                    else:
                        state.add_activity(f"Rejected '{node_name}' for run {execution_id[:8]}.")
                        st.rerun()

    col1, col2 = st.columns(2)
    if col1.button("Resume", type="primary", disabled=execution["status"] != "paused"):
        try:
            resumed = client.resume_execution(execution_id)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.current_dag_execution = resumed
            state.add_activity(f"Resumed run {execution_id[:8]} — status: {resumed['status']}.")
            st.rerun()
    if col2.button("Cancel", disabled=execution["status"] in {"completed", "failed", "cancelled"}):
        try:
            cancelled = client.cancel_execution(execution_id)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.current_dag_execution = cancelled
            state.add_activity(f"Cancelled run {execution_id[:8]}.")
            st.rerun()


def _render_graph(execution: dict[str, Any], client: APIClient) -> None:
    st.subheader("Dependency Graph")
    try:
        mermaid = client.get_execution_graph(execution["execution_id"])
    except APIClientError as exc:
        render_api_error(exc)
        return
    st.code(mermaid, language="mermaid")


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Execution",
    "Watch a run's live progress, per-step status, artifacts, and approvals — however it was started.",
    icon="▶️",
)

client = APIClient(state.backend_url)

_render_start_controls(state, client)
st.divider()

execution = state.current_dag_execution
if execution is not None:
    _render_progress(execution, client, state)
    st.divider()
    _render_nodes(execution)
    _render_artifacts(execution)
    st.divider()
    _render_approval_and_controls(execution, client, state)
    st.divider()
    _render_graph(execution, client)
