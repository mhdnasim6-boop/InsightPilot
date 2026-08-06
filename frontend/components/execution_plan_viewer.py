"""Execution plan viewer component: renders a PlannerOutput and its ExecutionPlan.

Read-only: this phase displays the planner's goal, steps, and validation
messages (``warnings``/``assumptions``) — no execution controls, per the
Planning page's scope.
"""

from typing import Any

import streamlit as st

from frontend.utils.formatting import format_number


def render_execution_plan(planner_output: dict[str, Any]) -> None:
    """Render a full PlannerOutput: goal, reasoning, plan metadata, steps, and warnings."""
    plan = planner_output.get("execution_plan") or {}

    st.markdown(f"**Goal:** {planner_output.get('goal') or plan.get('goal') or '—'}")
    if planner_output.get("reasoning_summary"):
        st.caption(planner_output["reasoning_summary"])

    col1, col2, col3 = st.columns(3)
    confidence = planner_output.get("confidence")
    col1.metric("Confidence", f"{confidence:.0%}" if confidence is not None else "—")
    col2.metric("Complexity", str(planner_output.get("estimated_complexity", "—")).title())
    col3.metric("Est. Duration (s)", format_number(planner_output.get("estimated_duration")))

    render_plan_steps(plan.get("steps", []))

    if planner_output.get("assumptions"):
        with st.expander("Assumptions"):
            for assumption in planner_output["assumptions"]:
                st.markdown(f"- {assumption}")

    for warning in planner_output.get("warnings", []):
        st.warning(warning)


def render_plan_steps(steps: list[dict[str, Any]]) -> None:
    """Render each ExecutionStep as an expandable row, in plan order."""
    if not steps:
        st.info("This plan has no steps.")
        return

    for index, step in enumerate(steps, start=1):
        title = f"{index}. {step.get('name', step.get('step_id', 'Step'))} — {step.get('status', 'pending')}"
        with st.expander(title):
            if step.get("description"):
                st.markdown(step["description"])
            st.caption(f"Node: `{step.get('node_name', '—')}`")
            if step.get("dependencies"):
                st.caption(f"Depends on: {', '.join(step['dependencies'])}")
            if step.get("inputs"):
                st.markdown("**Inputs**")
                st.json(step["inputs"])
            if step.get("outputs"):
                st.markdown("**Outputs**")
                st.json(step["outputs"])
