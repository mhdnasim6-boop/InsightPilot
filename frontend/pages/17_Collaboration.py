"""Collaboration page: start and drive an autonomous multi-agent collaboration
session — agents delegate work, exchange artifacts, and negotiate shared
dependencies through the CollaborationService, without a fully-enumerated
execution graph having to be built up front.

Distinct from the Execution page (which runs an already fully-expanded
``ExecutionPlan``): here, only the *first* SubTask is declared; the
Collaboration Coordinator can add more (dynamic follow-ups) as agents'
own results request them, and the task graph on screen grows to match.
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
    "skipped": "🟣",
}


def _status_label(status: str) -> str:
    return f"{_STATUS_ICONS.get(status, '')} {status}"


def _render_statistics(client: APIClient) -> None:
    st.subheader("Statistics")
    try:
        stats = client.get_collaboration_statistics()
    except APIClientError as exc:
        render_api_error(exc)
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sessions", stats["total_sessions"])
    col2.metric("Subtasks", stats["total_subtasks"])
    col3.metric("Messages", stats["total_messages"])
    col4.metric("Avg. subtasks/session", f"{stats['average_subtasks_per_session']:.1f}")
    if stats["by_status"]:
        st.caption("By status: " + ", ".join(f"{k} ({v})" for k, v in stats["by_status"].items()))


def _render_capabilities(client: APIClient) -> list[str]:
    with st.expander("Agent Capabilities"):
        try:
            capabilities = client.list_agent_capabilities()
        except APIClientError as exc:
            render_api_error(exc)
            return []
        st.dataframe(
            [
                {
                    "Agent": c["name"],
                    "Description": c["description"],
                    "Accepts": ", ".join(c["accepted_inputs"]) or "—",
                    "Produces": ", ".join(c["produced_outputs"]) or "—",
                    "Tools": ", ".join(c["supported_tools"]) or "—",
                    "Est. cost": c["estimated_cost"],
                    "Est. duration (s)": c["estimated_duration"],
                }
                for c in capabilities
            ],
            width="stretch",
            hide_index=True,
        )
        return [c["name"] for c in capabilities]


def _render_start_controls(state: Any, client: APIClient, agent_names: list[str]) -> None:
    st.subheader("Start a Collaboration Session")
    with st.form("start_collaboration_form"):
        goal = st.text_input("High-level goal", placeholder="Analyze sales.csv and produce a report")
        assigned_agent = st.selectbox("First agent to delegate to", agent_names or ["file_agent"])
        description = st.text_input("SubTask description", value="Initial delegation")
        submitted = st.form_submit_button("Start session", type="primary")

    if submitted:
        if not goal.strip():
            st.warning("Enter a goal first.")
            return
        try:
            task = client.start_collaboration(goal, assigned_agent, description, session_id=state.session_id)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.current_collaboration = task
            state.add_activity(f"Started collaboration '{task['collaboration_id']}'.")
            st.rerun()


def _render_delegate_controls(task: dict[str, Any], client: APIClient, state: Any, agent_names: list[str]) -> None:
    with st.expander("Delegate another SubTask"):
        collaboration_id = task["collaboration_id"]
        with st.form("delegate_subtask_form"):
            assigned_agent = st.selectbox("Agent", agent_names or ["report_agent"], key="delegate_agent")
            description = st.text_input("Description", value="Follow-up work", key="delegate_description")
            dependencies = st.multiselect("Depends on subtask(s)", task["subtask_order"], key="delegate_dependencies")
            submitted = st.form_submit_button("Delegate")

        if submitted:
            try:
                client.delegate_subtask(collaboration_id, assigned_agent, description, dependencies=dependencies)
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.current_collaboration = client.get_collaboration(collaboration_id)
                state.add_activity(f"Delegated a new '{assigned_agent}' subtask.")
                st.rerun()


def _render_progress(task: dict[str, Any]) -> None:
    st.subheader("Progress")
    subtasks = task["subtasks"]
    counts: dict[str, int] = {}
    for subtask in subtasks.values():
        counts[subtask["status"]] = counts.get(subtask["status"], 0) + 1
    total = len(subtasks) or 1
    completed = counts.get("completed", 0)
    st.progress(completed / total)
    cols = st.columns(len(_STATUS_ICONS))
    for col, (status, icon) in zip(cols, _STATUS_ICONS.items(), strict=False):
        col.metric(f"{icon} {status}", counts.get(status, 0))
    status_renderer = {"completed": st.success, "failed": st.error, "cancelled": st.error, "paused": st.warning}
    status_renderer.get(task["status"], st.info)(f"Collaboration `{task['collaboration_id']}` — status: **{task['status']}**")


def _render_task_graph(task: dict[str, Any]) -> None:
    st.subheader("Agent Assignments")
    rows = [
        {
            "SubTask": subtask_id[:8],
            "Agent": subtask["assigned_agent"],
            "Description": subtask["description"],
            "Status": _status_label(subtask["status"]),
            "Depends on": ", ".join(d[:8] for d in subtask["dependencies"]) or "—",
            "Error": subtask.get("error") or "—",
        }
        for subtask_id, subtask in task["subtasks"].items()
    ]
    st.dataframe(rows, width="stretch", hide_index=True)

    with st.expander("Artifact Graph (Mermaid)"):
        st.code(_build_mermaid(task), language="mermaid")

    with st.expander("SubTask Results"):
        for subtask_id, subtask in task["subtasks"].items():
            if subtask.get("result") is None:
                continue
            st.markdown(f"**{subtask_id[:8]}** (`{subtask['assigned_agent']}`)")
            st.json(subtask["result"], expanded=False)


def _build_mermaid(task: dict[str, Any]) -> str:
    lines = ["flowchart LR"]
    for subtask_id, subtask in task["subtasks"].items():
        label = f"{subtask['assigned_agent']}\\n{subtask['status']}"
        lines.append(f'  {subtask_id[:8]}["{label}"]')
    for subtask_id, subtask in task["subtasks"].items():
        for dependency in subtask["dependencies"]:
            lines.append(f"  {dependency[:8]} --> {subtask_id[:8]}")
    return "\n".join(lines)


def _render_message_stream(task: dict[str, Any], client: APIClient) -> None:
    st.subheader("Live Message Stream & Delegation History")
    try:
        history = client.get_collaboration_history(task["collaboration_id"])
    except APIClientError as exc:
        render_api_error(exc)
        return

    with st.expander(f"Messages ({len(history['messages'])})", expanded=True):
        for message in history["messages"]:
            target = message["to_agent"] or "(broadcast)"
            st.markdown(f"`{message['message_type']}` **{message['from_agent']}** → **{target}**: {message['content']}")

    with st.expander(f"Delegations ({len(history['delegations'])})"):
        st.dataframe(
            [
                {
                    "SubTask": d["subtask_id"][:8],
                    "From": d["from_agent"],
                    "To": d["to_agent"],
                    "Reason": d["reason"] or "—",
                }
                for d in history["delegations"]
            ],
            width="stretch",
            hide_index=True,
        )

    with st.expander(f"Artifact Exchanges ({len(history['artifact_exchanges'])})"):
        st.dataframe(
            [
                {
                    "Producer": e["producer_subtask_id"][:8],
                    "Consumer": e["consumer_subtask_id"][:8],
                    "Artifact keys": ", ".join(e["artifact_keys"]),
                }
                for e in history["artifact_exchanges"]
            ],
            width="stretch",
            hide_index=True,
        )

    if history["negotiations"]:
        with st.expander(f"Dependency Negotiations ({len(history['negotiations'])})"):
            st.dataframe(
                [
                    {
                        "Requested by": ", ".join(d[:8] for d in n["requested_by"]),
                        "Reused subtask": n["resolved_producer_subtask_id"][:8],
                        "Reason": n["reason"],
                    }
                    for n in history["negotiations"]
                ],
                width="stretch",
                hide_index=True,
            )


def _render_controls(task: dict[str, Any], client: APIClient, state: Any) -> None:
    st.subheader("Session Controls")
    collaboration_id = task["collaboration_id"]
    col1, col2, col3 = st.columns(3)

    if col1.button("Run", type="primary", disabled=task["status"] in {"completed", "failed", "cancelled"}):
        try:
            state.current_collaboration = client.run_collaboration(collaboration_id)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.add_activity(f"Ran collaboration {collaboration_id}.")
            st.rerun()

    if col2.button("Resume", disabled=task["status"] != "paused"):
        try:
            state.current_collaboration = client.resume_collaboration(collaboration_id)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.add_activity(f"Resumed collaboration {collaboration_id}.")
            st.rerun()

    if col3.button("Cancel", disabled=task["status"] in {"completed", "failed", "cancelled"}):
        try:
            state.current_collaboration = client.cancel_collaboration(collaboration_id)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.add_activity(f"Cancelled collaboration {collaboration_id}.")
            st.rerun()

    if st.button("Refresh"):
        try:
            state.current_collaboration = client.get_collaboration(collaboration_id)
        except APIClientError as exc:
            render_api_error(exc)
        st.rerun()


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Collaboration",
    "Autonomous multi-agent collaboration — agents delegate work, exchange artifacts, and "
    "negotiate shared dependencies, expanding the task graph dynamically.",
)

client = APIClient(state.backend_url)

_render_statistics(client)
st.divider()
agent_names = _render_capabilities(client)
st.divider()
_render_start_controls(state, client, agent_names)

task = state.current_collaboration
if task is not None:
    st.divider()
    _render_delegate_controls(task, client, state, agent_names)
    st.divider()
    _render_progress(task)
    st.divider()
    _render_task_graph(task)
    st.divider()
    _render_message_stream(task, client)
    st.divider()
    _render_controls(task, client, state)
