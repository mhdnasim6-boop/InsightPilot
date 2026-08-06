"""Autonomous page: the Autonomous Optimization & Self-Healing layer's own dashboard —
run a new analysis pass, browse past optimization reports, bottlenecks, performance
trends, healing recommendations, resource utilization, execution efficiency, and
cluster efficiency.

Requires authentication (Phase 35) — every ``/api/v1/autonomous/*`` endpoint is
permission-gated, same as every other protected router. Everything shown here is
advisory only: nothing on this page ever applies a recommendation.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state

_SEVERITY_ICONS = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
_VERDICT_ICONS = {"healthy": "🟢", "warning": "🟡", "critical": "🔴"}


def _authenticated_client(state: Any) -> APIClient:
    return APIClient(state.backend_url, access_token=state.access_token)


def _render_run_analysis(state: Any, client: APIClient) -> None:
    st.subheader("Run Analysis")
    st.caption(
        "Analyzes the platform's own current statistics (execution, workflow, "
        "distributed, federation, memory, reflection, adaptive planning) and produces a "
        "new, read-only OptimizationReport. Nothing is modified anywhere."
    )
    if st.button("Analyze now", type="primary"):
        try:
            report = client.run_autonomous_analysis()
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.add_activity(f"Generated optimization report '{report['report_id']}'.")
            st.rerun()


def _render_statistics(client: APIClient) -> None:
    st.subheader("Optimization Statistics")
    try:
        stats = client.get_autonomous_statistics()
    except APIClientError as exc:
        render_api_error(exc)
        return
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Reports", stats["total_reports"])
    col2.metric("Bottlenecks", stats["total_bottlenecks"])
    col3.metric("Actions", stats["total_actions"])
    col4.metric("Recommendations", stats["total_recommendations"])
    if stats["by_severity"]:
        st.caption(
            "By severity: "
            + ", ".join(f"{_SEVERITY_ICONS.get(k, '')} {k}: {v}" for k, v in stats["by_severity"].items())
        )
    if stats["last_analyzed_at"]:
        st.caption(f"Last analyzed: {stats['last_analyzed_at']}")


def _render_reports(client: APIClient) -> dict[str, Any] | None:
    st.subheader("Optimization Reports")
    try:
        reports = client.list_optimization_reports()
    except APIClientError as exc:
        render_api_error(exc)
        return None
    if not reports:
        st.caption("No optimization reports yet — click **Analyze now** above to generate one.")
        return None

    labels = [f"{r['report_id'][:12]} — {r['generated_at']}" for r in reversed(reports)]
    selected = st.selectbox("Select a report", options=range(len(labels)), format_func=lambda i: labels[i])
    report = list(reversed(reports))[selected]
    st.write(report["summary"])
    return report


def _render_decisions(report: dict[str, Any]) -> None:
    st.subheader("Analyzer Verdicts")
    st.dataframe(
        [
            {
                "Analyzer": d["analyzer_name"], "Verdict": f"{_VERDICT_ICONS.get(d['verdict'], '')} {d['verdict']}",
                "Bottlenecks": len(d["bottleneck_ids"]), "Notes": d["notes"],
            }
            for d in report["decisions"]
        ],
        width="stretch", hide_index=True,
    )


def _render_bottlenecks(report: dict[str, Any]) -> None:
    st.subheader("Bottlenecks")
    bottlenecks = report["bottlenecks"]
    if not bottlenecks:
        st.success("No bottlenecks detected in this report.")
        return
    st.dataframe(
        [
            {
                "Severity": f"{_SEVERITY_ICONS.get(b['severity'], '')} {b['severity']}", "Category": b["category"],
                "Title": b["title"], "Metric": b["metric_name"], "Value": round(b["metric_value"], 2),
                "Threshold": round(b["threshold"], 2), "Source": b["source"],
            }
            for b in bottlenecks
        ],
        width="stretch", hide_index=True,
    )


def _render_actions_and_recommendations(report: dict[str, Any]) -> None:
    st.subheader("Suggested Actions")
    actions = report["actions"]
    if actions:
        st.dataframe(
            [{"Impact": a["estimated_impact"], "Category": a["category"], "Title": a["title"], "Description": a["description"]} for a in actions],
            width="stretch", hide_index=True,
        )
    else:
        st.caption("No suggested actions in this report.")

    st.subheader("Healing Recommendations")
    st.caption("Advisory only — every recommendation requires human review; nothing here is ever applied automatically.")
    recommendations = report["recommendations"]
    if recommendations:
        st.dataframe(
            [
                {
                    "Risk": r["risk_level"], "Strategy": r["strategy_name"], "Title": r["title"],
                    "Rationale": r["rationale"],
                }
                for r in recommendations
            ],
            width="stretch", hide_index=True,
        )
    else:
        st.caption("No healing recommendations in this report.")


def _render_performance_profile(report: dict[str, Any]) -> None:
    st.subheader("Performance Profile Snapshot")
    profile = report["performance_profile"]

    st.markdown("**Execution efficiency**")
    exec_metrics = profile["execution_metrics"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Traces", exec_metrics["trace_count"])
    col2.metric("Avg execution (ms)", round(exec_metrics["average_execution_time_ms"], 1))
    col3.metric("Tool calls", exec_metrics["number_of_tool_calls"])
    col4.metric("Avg approval latency (ms)", round(exec_metrics["average_approval_latency_ms"], 1))

    st.markdown("**Worker & cluster efficiency**")
    workers = profile["worker_fleet_statistics"]
    federation = profile["federation_statistics"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Workers online/total", f"{workers['online_workers']}/{workers['total_workers']}")
    col2.metric("Worker capacity used", f"{workers['total_active_tasks']}/{workers['total_capacity']}")
    col3.metric("Clusters online/total", f"{federation['online_clusters']}/{federation['total_clusters']}")
    col4.metric("Cluster capacity used", f"{federation['active_remote_executions']}/{federation['total_capacity']}")

    st.markdown("**Resource utilization**")
    memory = profile["memory_statistics"]
    col1, col2, col3 = st.columns(3)
    col1.metric("Memory items", memory["total_items"])
    col2.metric("Avg importance", round(memory["average_importance"], 2))
    col3.metric("Audit events", profile["audit_event_count"])


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Autonomous",
    "Autonomous Optimization & Self-Healing — continuously analyzes the platform's own "
    "execution history, performance, failures, and resource utilization, then surfaces "
    "bottlenecks and advisory-only recommendations. Nothing on this page is ever applied "
    "automatically; every action and recommendation requires a human decision.",
)

if not state.is_authenticated:
    st.info("Log in on the **Settings** page first — every autonomous endpoint requires authentication.")
else:
    client = _authenticated_client(state)
    _render_run_analysis(state, client)
    st.divider()
    _render_statistics(client)
    st.divider()
    report = _render_reports(client)
    if report is not None:
        st.divider()
        _render_decisions(report)
        st.divider()
        _render_bottlenecks(report)
        st.divider()
        _render_actions_and_recommendations(report)
        st.divider()
        _render_performance_profile(report)
