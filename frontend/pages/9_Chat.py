"""Chat page: ask questions about the current dataset, analysis, visualization,
plan, report, workflow, reflection, or optimization — InsightPilot's copilot.

Presentation only — every fact in an answer came from the backend's
``ChatService``; this page never computes anything, it only renders the
conversation and whatever the response says it referenced.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error, render_chart, render_kpi_cards
from frontend.layouts import ensure_session, page_header, render_sidebar
from frontend.state import get_dashboard_state
from frontend.utils import (
    build_chat_context,
    find_referenced_charts,
    find_referenced_kpis,
    generate_starter_prompts,
)

# metadata key -> (page path, button label). ChatResponse.metadata carries at
# most one of these (see backend.chatbot.retrieval.context_builder's own
# _deep_link_metadata) — never anything the model itself produced.
_DEEP_LINKS: dict[str, tuple[str, str]] = {
    "report_id": ("pages/11_Reports.py", "📄 Open in Reports"),
    "workflow_id": ("pages/23_Workflows.py", "🔧 Open in Workflows"),
    "reflection_id": ("pages/18_Reflection.py", "🪞 Open in Reflection"),
    "optimization_id": ("pages/19_Adaptive.py", "⚙️ Open in Adaptive"),
}


def _render_referenced_items(message: dict[str, Any]) -> None:
    state = get_dashboard_state()

    if (message.get("metadata") or {}).get("fallback_reason") == "ollama_unreachable":
        st.warning("Local AI model is unavailable. Falling back to development mode.")

    kpi_names = message.get("referenced_kpis") or []
    analysis = state.current_analysis
    if kpi_names and analysis:
        matched = find_referenced_kpis(analysis["kpis"], kpi_names)
        if matched:
            st.caption("Referenced KPIs")
            render_kpi_cards(matched)
            with st.expander("View as table"):
                st.dataframe(matched, width="stretch", hide_index=True)

    chart_ids = message.get("referenced_charts") or []
    visualization = state.current_visualization
    if chart_ids and visualization:
        matched_charts = find_referenced_charts(
            visualization["visualization_result"]["charts"], visualization["rendered_charts"], chart_ids
        )
        if matched_charts:
            st.caption("Referenced charts")
            for chart_spec, figure_json in matched_charts:
                render_chart(chart_spec, figure_json, key=f"chat_chart_{message['timestamp']}_{chart_spec['chart_id']}")

    insights = message.get("referenced_insights") or []
    if insights:
        st.caption("Referenced insights")
        for insight in insights:
            st.markdown(f"- {insight}")

    metadata = message.get("metadata") or {}
    for meta_key, (page_path, label) in _DEEP_LINKS.items():
        if metadata.get(meta_key):
            if st.button(label, key=f"deep_link_{message['timestamp']}_{meta_key}"):
                st.switch_page(page_path)
            break


def _ask(question: str, client: APIClient, session_id: str) -> bool:
    """Ask one question and append the answer to history. Returns whether it succeeded."""
    state = get_dashboard_state()
    state.add_chat_message("user", question)

    # Streaming-response placeholder: this phase calls AIService.generate(), not
    # .stream() — a future phase can swap this spinner for real token-by-token output.
    with st.spinner("Thinking..."):
        try:
            context = build_chat_context(session_id, state)
            response = client.ask_chat(question, context)
        except APIClientError as exc:
            render_api_error(exc)
            return False

    state.add_chat_message(
        "assistant",
        response["answer"],
        intent=response["intent"],
        confidence=response["confidence"],
        answerable=response["answerable"],
        referenced_kpis=response["referenced_kpis"],
        referenced_charts=response["referenced_charts"],
        referenced_insights=response["referenced_insights"],
        suggested_follow_up_questions=response["suggested_follow_up_questions"],
        metadata=response.get("metadata") or {},
    )
    return True


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Chat", "Your AI copilot — ask about your dataset, analysis, charts, plans, reports, workflows, "
    "reflections, or optimizations. It never repeats a question you've already answered.", icon="💬",
)

if state.selected_dataset is None:
    st.info("No dataset selected yet — you can still ask general questions, or upload a dataset first.")

session_id = ensure_session(state)

for message in state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            _render_referenced_items(message)

last_message = state.chat_history[-1] if state.chat_history else None
suggestions = (
    last_message.get("suggested_follow_up_questions") or generate_starter_prompts(state)
    if last_message and last_message["role"] == "assistant"
    else generate_starter_prompts(state)
)

st.caption("Suggested questions")
suggestion_cols = st.columns(len(suggestions))
clicked_suggestion = None
for col, suggestion in zip(suggestion_cols, suggestions, strict=True):
    with col:
        if st.button(suggestion, key=f"suggestion_{suggestion}", width="stretch"):
            clicked_suggestion = suggestion

col1, col2 = st.columns([5, 1])
with col2:
    if st.button("Clear conversation", width="stretch"):
        state.clear_chat_history()
        st.rerun()

typed_question = st.chat_input("Ask a question about your data...")
question = typed_question or clicked_suggestion

if question and session_id is not None:
    client = APIClient(state.backend_url)
    if _ask(question, client, session_id):
        st.rerun()
elif question and session_id is None:
    render_api_error(APIClientError("No active session and the backend is unreachable."))
