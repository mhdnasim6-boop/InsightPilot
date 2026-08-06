"""Reflection page: generate and browse deterministic post-execution reviews —
what happened, what succeeded/failed/was slow, and what to do differently
next time. Not AI-generated commentary: every score/strength/weakness/
recommendation here is a plain function of the same ExecutionTrace/
approval/memory/collaboration data the Observability/Approval/Memory/
Collaboration pages already show, just interpreted.

Reuses ``state.current_plan_execution``/``state.current_dag_execution``
(whichever the user last ran) as the plan to reflect on — no new
plan-generation UI here, mirroring the Execution page's own reuse of
``state.current_plan``.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state

_LABEL_ICONS = {"excellent": "🟢", "good": "🔵", "needs_improvement": "🟠", "poor": "🔴"}


def _score_metric(column: Any, title: str, score: dict[str, Any]) -> None:
    icon = _LABEL_ICONS.get(score["label"], "")
    column.metric(title, f"{score['value']:.0f}/100", help=f"{icon} {score['label']}")


def _render_statistics(client: APIClient) -> None:
    st.subheader("Statistics")
    try:
        stats = client.get_reflection_statistics()
    except APIClientError as exc:
        render_api_error(exc)
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Reflections", stats["total_reflections"])
    col2.metric("Successful", stats["success_count"])
    col3.metric("Avg. execution score", f"{stats['average_execution_score']:.0f}")
    col4.metric("Recommendations", stats["total_recommendations"])
    if stats["by_label"]:
        st.caption("By label: " + ", ".join(f"{k} ({v})" for k, v in stats["by_label"].items()))


def _render_generate_controls(state: Any, client: APIClient) -> None:
    st.subheader("Generate a Reflection")
    plan_execution = state.current_dag_execution or state.current_plan_execution
    if plan_execution is None:
        st.info("Run a plan on the Execution or Planning page first, then come back here to reflect on it.")
        return

    plan = state.current_plan["execution_plan"] if state.current_plan else None
    if plan is None:
        st.info("No generated plan available to reflect on.")
        return

    st.caption(f"Ready to reflect on: **{plan.get('goal') or plan['plan_id']}**")
    collaboration_id = None
    if state.current_collaboration is not None:
        collaboration_id = state.current_collaboration["collaboration_id"]
        st.caption(f"Will also fold in collaboration session `{collaboration_id}`.")

    if st.button("Generate reflection", type="primary"):
        try:
            reflection = client.generate_reflection({**plan, "status": "ready"}, collaboration_id=collaboration_id)
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.current_reflection = reflection
            state.add_activity(f"Generated reflection '{reflection['reflection_id']}'.")
            st.rerun()


def _render_review(reflection: dict[str, Any]) -> None:
    review = reflection["review"]
    status_renderer = st.success if review["overall_success"] else st.warning
    status_renderer(f"Reflection `{reflection['reflection_id']}` — overall {'success' if review['overall_success'] else 'not fully successful'}.")

    col1, col2, col3 = st.columns(3)
    _score_metric(col1, "Execution score", review["execution_score"])
    _score_metric(col2, "Efficiency score", review["efficiency_score"])
    _score_metric(col3, "Confidence score", review["confidence_score"])

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Strengths**")
        for strength in review["strengths"] or ["*(none)*"]:
            st.markdown(f"- {strength}")
    with col2:
        st.markdown("**Weaknesses**")
        for weakness in review["weaknesses"] or ["*(none)*"]:
            st.markdown(f"- {weakness}")

    st.markdown("**Recommendations**")
    if review["recommendations"]:
        st.dataframe(
            [
                {"Priority": r["priority"], "Category": r["category"], "Message": r["message"], "Reason": r["reason"]}
                for r in review["recommendations"]
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("None.")

    st.markdown("**Future Improvements**")
    if review["future_improvements"]:
        for improvement in review["future_improvements"]:
            st.markdown(f"- **{improvement['area']}:** {improvement['description']} ({improvement['expected_impact']})")
    else:
        st.caption("None.")


def _render_summaries(reflection: dict[str, Any]) -> None:
    review = reflection["review"]
    col1, col2 = st.columns(2)

    with col1:
        with st.expander("Tool & Agent Activity", expanded=True):
            st.json(review["tool_summary"], expanded=False)
        with st.expander("Approval Summary"):
            st.json(review["approval_summary"], expanded=False)

    with col2:
        with st.expander("Memory Reuse", expanded=True):
            st.json(review["memory_summary"], expanded=False)
        with st.expander("Collaboration Summary"):
            st.json(review["collaboration_summary"], expanded=False)


def _render_export(reflection: dict[str, Any], client: APIClient) -> None:
    st.subheader("Export")
    col1, col2 = st.columns(2)
    reflection_id = reflection["reflection_id"]

    if col1.button("Export JSON"):
        try:
            content = client.export_reflection(reflection_id, "json")
        except APIClientError as exc:
            render_api_error(exc)
        else:
            st.download_button("Download JSON", content, file_name=f"reflection_{reflection_id}.json", key="reflection_export_json")

    if col2.button("Export Markdown"):
        try:
            content = client.export_reflection(reflection_id, "markdown")
        except APIClientError as exc:
            render_api_error(exc)
        else:
            st.download_button("Download Markdown", content, file_name=f"reflection_{reflection_id}.md", key="reflection_export_md")


def _render_timeline(client: APIClient, state: Any) -> None:
    st.subheader("Timeline")
    try:
        reflections = client.list_reflections()
    except APIClientError as exc:
        render_api_error(exc)
        return

    if not reflections:
        st.info("No reflections generated yet.")
        return

    options = {f"{r['plan_id']} — {r['generated_at']}": r["reflection_id"] for r in reflections}
    chosen_label = st.selectbox("Browse a previous reflection", list(options.keys()))
    if st.button("Load selected reflection"):
        try:
            state.current_reflection = client.get_reflection(options[chosen_label])
        except APIClientError as exc:
            render_api_error(exc)
        else:
            st.rerun()

    st.dataframe(
        [
            {
                "Reflection": r["reflection_id"][:8],
                "Plan": r["plan_id"][:8],
                "Score": round(r["review"]["execution_score"]["value"]),
                "Success": r["review"]["overall_success"],
                "Generated": r["generated_at"],
            }
            for r in reflections
        ],
        width="stretch",
        hide_index=True,
    )


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Reflection",
    "Deterministic post-execution review — what happened, what succeeded/failed/was slow, "
    "and what to do differently next time.",
)

client = APIClient(state.backend_url)

_render_statistics(client)
st.divider()
_render_generate_controls(state, client)

reflection = state.current_reflection
if reflection is not None:
    st.divider()
    _render_review(reflection)
    st.divider()
    _render_summaries(reflection)
    st.divider()
    _render_export(reflection, client)

st.divider()
_render_timeline(client, state)
