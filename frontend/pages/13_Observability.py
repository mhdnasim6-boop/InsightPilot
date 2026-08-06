"""Observability page: execution traces, timelines, and agent/tool/AI metrics.

Read-only, like the MCP page: every value here comes straight from
``GET /observability/*`` — no observability logic lives on the
frontend. A trace exists for every plan that has ever started
executing (even ones still RUNNING/PAUSED), so this page doubles as a
live view of in-flight plans and a historical record of finished ones.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state

_STATUS_ICONS = {
    "running": "🟡",
    "paused": "🟠",
    "completed": "🟢",
    "failed": "🔴",
    "cancelled": "⚪",
}


def _status_label(status: str) -> str:
    return f"{_STATUS_ICONS.get(status, '')} {status}"


def _render_overview(client: APIClient) -> None:
    st.subheader("Overview")
    try:
        summary = client.get_metrics_summary()
    except APIClientError as exc:
        render_api_error(exc)
        return

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Traces", summary["trace_count"])
    col2.metric("Avg. execution time", f"{summary['average_execution_time_ms']:.0f}ms")
    col3.metric("Tool calls", summary["number_of_tool_calls"])
    col4.metric("AI calls", summary["number_of_ai_calls"])
    col5.metric("Approvals", summary["number_of_approvals"])
    if summary["number_of_approvals"]:
        st.caption(f"Average approval latency: {summary['average_approval_latency_ms']:.0f}ms")


def _render_agent_metrics(client: APIClient) -> None:
    st.subheader("Agent Metrics")
    try:
        metrics = client.get_agent_metrics()
    except APIClientError as exc:
        render_api_error(exc)
        return
    if not metrics:
        st.caption("No agent activity recorded yet.")
        return
    st.dataframe(
        [
            {
                "Agent": m["agent_name"],
                "Calls": m["call_count"],
                "Completed": m["completed_count"],
                "Failed": m["failed_count"],
                "Avg. Duration": f"{m['average_duration_ms']:.0f}ms",
                "Tool Calls": m["total_tool_calls"],
            }
            for m in metrics
        ],
        width="stretch",
        hide_index=True,
    )


def _render_tool_metrics(client: APIClient) -> None:
    st.subheader("Tool Metrics")
    try:
        metrics = client.get_tool_metrics()
    except APIClientError as exc:
        render_api_error(exc)
        return
    if not metrics:
        st.caption("No tool activity recorded yet.")
        return
    st.dataframe(
        [
            {
                "Tool": m["tool_name"],
                "Calls": m["call_count"],
                "Completed": m["completed_count"],
                "Failed": m["failed_count"],
                "Avg. Duration": f"{m['average_duration_ms']:.0f}ms",
            }
            for m in metrics
        ],
        width="stretch",
        hide_index=True,
    )


def _render_ai_metrics(client: APIClient) -> None:
    st.subheader("AI Metrics")
    try:
        metrics = client.get_ai_metrics()
    except APIClientError as exc:
        render_api_error(exc)
        return
    if metrics["call_count"] == 0:
        st.caption("No AI calls recorded yet.")
        return
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Calls", metrics["call_count"])
    col2.metric("Total Tokens", metrics["total_tokens"])
    col3.metric("Avg. Latency", f"{metrics['average_latency_ms']:.0f}ms")
    col4.metric("Est. Cost", f"${metrics['total_estimated_cost']:.4f}")


def _render_trace_detail(client: APIClient, trace: dict[str, Any]) -> None:
    st.markdown(f"**Status:** {_status_label(trace['status'])}  ")
    st.markdown(f"**Plan:** `{trace['plan_id']}`  ")
    duration = f"{trace['duration_ms']:.0f}ms" if trace.get("duration_ms") is not None else "in progress"
    st.markdown(f"**Duration:** {duration}")

    tab_timeline, tab_agents, tab_tools, tab_ai, tab_approvals, tab_export = st.tabs(
        ["Timeline", "Agents", "Tools", "AI Calls", "Approvals", "Export"]
    )

    with tab_timeline:
        try:
            timeline = client.get_trace_timeline(trace["trace_id"])
        except APIClientError as exc:
            render_api_error(exc)
        else:
            if not timeline:
                st.caption("Nothing recorded yet.")
            for entry in timeline:
                duration_label = f"{entry['duration_ms']:.0f}ms" if entry.get("duration_ms") is not None else "…"
                st.markdown(f"- `{entry['kind']}` **{entry['name']}** — {entry['status']} ({duration_label})")

    with tab_agents:
        if not trace["agent_traces"]:
            st.caption("No agents ran yet.")
        else:
            st.dataframe(
                [
                    {
                        "Agent": a["agent_name"],
                        "Status": a["status"],
                        "Duration": f"{a['duration_ms']:.0f}ms",
                        "Tool Calls": len(a["tool_calls"]),
                    }
                    for a in trace["agent_traces"]
                ],
                width="stretch",
                hide_index=True,
            )

    with tab_tools:
        if not trace["tool_traces"]:
            st.caption("No tools called yet.")
        else:
            st.dataframe(
                [
                    {
                        "Tool": t["tool_name"],
                        "Agent": t.get("agent_name") or "—",
                        "Status": t["status"],
                        "Duration": f"{t['duration_ms']:.0f}ms",
                    }
                    for t in trace["tool_traces"]
                ],
                width="stretch",
                hide_index=True,
            )

    with tab_ai:
        if not trace["ai_calls"]:
            st.caption("No AI calls made yet.")
        else:
            st.dataframe(
                [
                    {
                        "Provider": c["provider"],
                        "Model": c["model"],
                        "Tokens": c["tokens"]["total_tokens"],
                        "Latency": f"{c['latency_ms']:.0f}ms",
                        "Cost": f"${c['estimated_cost']:.4f}",
                    }
                    for c in trace["ai_calls"]
                ],
                width="stretch",
                hide_index=True,
            )

    with tab_approvals:
        if not trace["approval_traces"]:
            st.caption("No approvals requested for this plan.")
        else:
            for approval in trace["approval_traces"]:
                node_name = approval["metadata"].get("node_name", "unknown agent")
                st.markdown(f"- **{node_name}** — {approval['status']} (step `{approval['step_id']}`)")

    with tab_export:
        export_format = st.selectbox("Format", ["json", "markdown", "csv"], key="observability_export_format")
        if st.button("Export"):
            try:
                content = client.export_trace(trace["trace_id"], export_format=export_format)
            except APIClientError as exc:
                render_api_error(exc)
            else:
                extension = {"json": "json", "markdown": "md", "csv": "csv"}[export_format]
                st.download_button(
                    "Download",
                    content,
                    file_name=f"trace-{trace['trace_id']}.{extension}",
                    key="observability_export_download",
                )
                st.code(content[:2000], language=export_format if export_format != "csv" else "text")

    if trace["errors"] or trace["warnings"]:
        with st.expander("Errors & Warnings"):
            for error in trace["errors"]:
                st.error(error)
            for warning in trace["warnings"]:
                st.warning(warning)


def _render_trace_viewer(client: APIClient) -> None:
    st.subheader("Trace Viewer")
    try:
        traces = client.list_traces()
    except APIClientError as exc:
        render_api_error(exc)
        return

    if not traces:
        st.info("No executions have been traced yet — run a plan on the Planning page first.")
        return

    options = {
        f"{_status_label(t['status'])} · {t['trace_id'][:8]} · plan {t['plan_id'][:8]}": t["trace_id"]
        for t in traces
    }
    chosen_label = st.selectbox("Select a trace", list(options.keys()))
    trace_id = options[chosen_label]

    try:
        trace = client.get_trace(trace_id)
    except APIClientError as exc:
        render_api_error(exc)
        return

    with st.container(border=True):
        _render_trace_detail(client, trace)


state = get_dashboard_state()
render_sidebar(state)
page_header("Observability", "Execution traces, timelines, and agent/tool/AI metrics for every plan run.")

client = APIClient(state.backend_url)

_render_overview(client)
st.divider()
col1, col2 = st.columns(2)
with col1:
    _render_agent_metrics(client)
with col2:
    _render_tool_metrics(client)
_render_ai_metrics(client)
st.divider()
_render_trace_viewer(client)
