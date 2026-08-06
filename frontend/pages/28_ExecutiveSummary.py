"""Executive Summary page: write a grounded, one-page executive summary from an
already-generated report.

Extracted from the old Planning page (Phase v1.0 navigation redesign) into its
own page under the Reports section — the underlying call
(``POST /agents/executive-summary/execute``) and state slot
(``state.current_executive_summary_execution``) are unchanged; only the page it
lives on and its user-facing wording changed (no "ExecutiveSummaryAgent"/"Browser
Agent" class names in the UI — those are backend implementation details).
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error, render_empty_state
from frontend.layouts import ensure_session, page_header, render_sidebar
from frontend.state import get_dashboard_state


def _render_generation_controls(state: Any, client: APIClient, session_id: str | None) -> None:
    report_document = state.current_report

    browser_result = state.current_browser_execution
    include_web_research = False
    if browser_result and browser_result.get("status") == "completed":
        include_web_research = st.checkbox(
            "Include external web research in the summary", value=True, key="executive_summary_include_research"
        )

    if st.button("Generate Executive Summary", type="primary"):
        if session_id is None:
            render_api_error(APIClientError("No active session and the backend is unreachable."))
            return

        result: dict[str, Any] | None
        with st.spinner("Writing executive summary..."):
            try:
                result = client.execute_executive_summary_agent(
                    session_id,
                    report_document=report_document,
                    browser_agent_result=browser_result if include_web_research else None,
                )
            except APIClientError as exc:
                render_api_error(exc)
                result = None

        if result is not None:
            state.current_executive_summary_execution = result
            if result["status"] == "completed":
                state.add_activity(f"Generated an executive summary for '{report_document['title']}'.")
            else:
                state.add_activity("Executive summary generation failed.")


def _render_result(result: dict[str, Any]) -> None:
    status = result["status"]
    summary = f"Executive summary {status} in {result.get('execution_time', 0.0):.2f}s"
    if status == "completed":
        st.success(summary)
    else:
        st.error(summary)
    for warning in result.get("warnings", []):
        st.warning(warning)

    if result.get("executive_summary"):
        st.markdown("**Executive Summary**")
        st.write(result["executive_summary"])

    if result.get("key_findings"):
        st.markdown("**Key Findings**")
        for finding in result["key_findings"]:
            st.markdown(f"- {finding}")

    if result.get("risks"):
        st.markdown("**Key Risks**")
        for risk in result["risks"]:
            st.markdown(f"- {risk}")

    if result.get("recommendations"):
        st.markdown("**Recommendations**")
        for recommendation in result["recommendations"]:
            st.markdown(f"- {recommendation}")

    if result.get("follow_up_actions"):
        st.markdown("**Suggested Next Actions**")
        for action in result["follow_up_actions"]:
            st.markdown(f"- {action}")

    if "confidence" in result:
        st.caption(f"Confidence: {result['confidence']:.0%}")


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Executive Summary",
    "A grounded, one-page summary written from an already-generated report — never a new "
    "number, KPI, chart, or trend beyond what the report already contains.",
    icon="📝",
)

session_id = ensure_session(state)

if state.current_report is None:
    clicked = render_empty_state(
        "No report to summarize yet",
        "Generate a report on the Reports page first, then come back here to write its executive summary.",
        icon="📑",
        action_label="Go to Reports",
        key="executive_summary_go_to_reports",
    )
    if clicked:
        st.switch_page("pages/11_Reports.py")
else:
    client = APIClient(state.backend_url)
    st.caption(f"Summarizing: **{state.current_report['title']}**")
    _render_generation_controls(state, client, session_id)

    if state.current_executive_summary_execution is not None:
        st.divider()
        _render_result(state.current_executive_summary_execution)
