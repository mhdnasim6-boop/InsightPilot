"""Adaptive page: deterministically optimize the currently generated plan
against historical evidence (reflections, collaboration outcomes, memory
reuse) — before/after plan comparison, estimated savings, and the exact
reasoning behind every suggestion.

Reuses ``state.current_plan`` (the same plan the Planning/Execution pages
already show) as the plan to optimize — no new plan-generation UI here,
mirroring the Execution/Reflection pages' own reuse of that state slot.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state


def _render_statistics(client: APIClient) -> None:
    st.subheader("Statistics")
    try:
        stats = client.get_adaptive_statistics()
    except APIClientError as exc:
        render_api_error(exc)
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Optimizations", stats["total_optimizations"])
    col2.metric("Decisions", stats["total_decisions"])
    col3.metric("Applied", stats["applied_decision_count"])
    col4.metric("Est. savings (s)", f"{stats['total_estimated_execution_savings_seconds']:.1f}")
    if stats["by_category"]:
        st.caption("By category: " + ", ".join(f"{k} ({v})" for k, v in stats["by_category"].items()))


def _render_controls(state: Any, client: APIClient) -> None:
    st.subheader("Optimize the Current Plan")
    if state.current_plan is None:
        st.info("Generate a plan on the Planning page first, then come back here to optimize it.")
        return

    plan = state.current_plan["execution_plan"]
    st.caption(f"Ready to optimize: **{plan.get('goal') or plan['plan_id']}** ({len(plan['steps'])} step(s))")

    col1, col2 = st.columns(2)
    if col1.button("Preview (explain)", help="See what would be suggested — no memory write."):
        try:
            state.current_optimization = client.explain_plan_optimization(plan, session_id=state.session_id)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            st.rerun()

    if col2.button("Optimize & Remember", type="primary"):
        try:
            state.current_optimization = client.optimize_plan(plan, session_id=state.session_id)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.add_activity(f"Optimized plan '{plan['plan_id']}'.")
            st.rerun()


def _render_savings(optimization: dict[str, Any]) -> None:
    st.subheader("Estimated Savings")
    col1, col2, col3 = st.columns(3)
    col1.metric("Execution savings", f"{optimization['execution_savings_estimate_seconds']:.1f}s")
    col2.metric("Approval savings", optimization["approval_savings_estimate"])
    col3.metric("Parallelism improved", "Yes" if optimization["parallelism_improved"] else "No")


def _render_before_after(optimization: dict[str, Any]) -> None:
    st.subheader("Before vs. After")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Original plan**")
        st.dataframe(
            [{"Step": s["step_id"], "Agent": s["node_name"], "Depends on": ", ".join(s["dependencies"]) or "—"} for s in optimization["original_plan"]["steps"]],
            width="stretch",
            hide_index=True,
        )
    with col2:
        st.markdown("**Optimized plan**")
        st.dataframe(
            [{"Step": s["step_id"], "Agent": s["node_name"], "Depends on": ", ".join(s["dependencies"]) or "—"} for s in optimization["optimized_plan"]["steps"]],
            width="stretch",
            hide_index=True,
        )


def _render_decisions(optimization: dict[str, Any]) -> None:
    st.subheader("Suggested Improvements & Reasoning")
    decisions = optimization["decisions"]
    if not decisions:
        st.info("No optimization decisions — not enough repeated historical evidence yet.")
        return
    st.dataframe(
        [
            {
                "Applied": "✅" if d["applied"] else "—",
                "Category": d["category"],
                "Suggestion": d["message"],
                "Reason": d["reason"],
                "Evidence": d["evidence_count"],
            }
            for d in decisions
        ],
        width="stretch",
        hide_index=True,
    )


def _render_evidence(optimization: dict[str, Any]) -> None:
    with st.expander("Historical Evidence (Planning Context)"):
        context = optimization["planning_context"]
        st.markdown("**Reflection patterns**")
        st.json(context["reflection_patterns"], expanded=False)
        st.markdown("**Execution patterns**")
        st.json(context["execution_patterns"], expanded=False)
        st.markdown("**Collaboration patterns**")
        st.json(context["collaboration_patterns"], expanded=False)
        st.markdown("**Tool patterns**")
        st.json(context["tool_patterns"], expanded=False)


def _render_export(optimization: dict[str, Any], client: APIClient) -> None:
    optimization_id = optimization["optimization_id"]
    if not optimization_id:
        st.caption("This is a preview (from 'explain') — nothing stored to export yet.")
        return
    st.subheader("Export")
    col1, col2 = st.columns(2)
    if col1.button("Export JSON"):
        try:
            content = client.export_optimization(optimization_id, "json")
        except APIClientError as exc:
            render_api_error(exc)
        else:
            st.download_button("Download JSON", content, file_name=f"optimization_{optimization_id}.json", key="adaptive_export_json")
    if col2.button("Export Markdown"):
        try:
            content = client.export_optimization(optimization_id, "markdown")
        except APIClientError as exc:
            render_api_error(exc)
        else:
            st.download_button("Download Markdown", content, file_name=f"optimization_{optimization_id}.md", key="adaptive_export_md")


def _render_history(client: APIClient) -> None:
    st.subheader("History")
    try:
        history = client.get_adaptive_history()
    except APIClientError as exc:
        render_api_error(exc)
        return
    if not history:
        st.info("No optimizations generated yet.")
        return
    st.dataframe(
        [
            {
                "Optimization": o["optimization_id"][:8],
                "Plan": o["plan_id"][:8],
                "Decisions": len(o["decisions"]),
                "Applied": sum(1 for d in o["decisions"] if d["applied"]),
                "Generated": o["generated_at"],
            }
            for o in history
        ],
        width="stretch",
        hide_index=True,
    )


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Adaptive",
    "Deterministic plan optimization — improving future plans from prior reflections, "
    "execution history, collaboration outcomes, and memory reuse.",
)

client = APIClient(state.backend_url)

_render_statistics(client)
st.divider()
_render_controls(state, client)

optimization = state.current_optimization
if optimization is not None:
    st.divider()
    _render_savings(optimization)
    st.divider()
    _render_before_after(optimization)
    st.divider()
    _render_decisions(optimization)
    st.divider()
    _render_evidence(optimization)
    st.divider()
    _render_export(optimization, client)

st.divider()
_render_history(client)
