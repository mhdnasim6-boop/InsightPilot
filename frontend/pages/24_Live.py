"""Live page: the Realtime Event Streaming layer's own dashboard —
live workflow/step/agent/tool/AI/memory/approval/plugin/security events,
filterable by workflow/trace/agent/event type, with pause/resume and
replay history.

Each rerun of the ``_live_feed`` fragment (below) opens one short,
bounded connection to ``/ws/events`` (via ``APIClient.stream_realtime_events``),
collects whatever arrives within a couple of seconds, then closes —
Streamlit has no persistent-connection-across-reruns primitive, so this
is the same "poll a fragment" idiom every live Streamlit dashboard uses;
the underlying transport between backend and this page is still the
real, push-based WebSocket, not a REST poll — confirmed by the endpoint
this calls (``/ws/events``), not ``GET /replay``, which is reserved for
the explicit "load history" action below.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state

_CATEGORY_ICONS: dict[str, str] = {
    "workflow": "🧩", "step": "🔹", "agent": "🤖", "tool": "🛠️", "ai": "✨",
    "approval": "✅", "memory": "🧠", "reflection": "🪞", "optimization": "⚡",
    "plugin": "🔌", "security": "🔐",
}


def _category_of(event_type: str) -> str:
    for prefix, category in (
        ("workflow", "workflow"), ("step", "step"), ("agent", "agent"), ("tool", "tool"),
        ("ai_call", "ai"), ("approval", "approval"), ("memory", "memory"),
        ("reflection", "reflection"), ("optimization", "optimization"),
        ("plugin", "plugin"), ("user_logged", "security"),
    ):
        if event_type.startswith(prefix):
            return category
    return "workflow"


def _authenticated_client(state: Any) -> APIClient:
    return APIClient(state.backend_url, access_token=state.access_token)


def _render_filters(state: Any, client: APIClient) -> dict[str, Any]:
    st.subheader("Filters")
    try:
        event_types = client.list_realtime_event_types()
    except APIClientError as exc:
        render_api_error(exc)
        event_types = []

    filters = state.live_filters
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_types = st.multiselect("Event types", options=event_types, default=filters.get("event_types", []))
    with col2:
        agent_name = st.text_input("Agent name", value=filters.get("agent_name", ""))
    col3, col4 = st.columns(2)
    with col3:
        workflow_id = st.text_input("Workflow ID", value=filters.get("workflow_id", ""))
    with col4:
        trace_id = st.text_input("Trace ID", value=filters.get("trace_id", ""))

    new_filters = {
        "event_types": selected_types, "workflow_id": workflow_id, "trace_id": trace_id, "agent_name": agent_name,
    }
    state.live_filters = new_filters
    return new_filters


def _render_controls(state: Any, client: APIClient, filters: dict[str, Any]) -> None:
    col1, col2, col3, col4 = st.columns(4)
    if col1.button("⏸️ Pause" if not state.live_stream_paused else "▶️ Resume"):
        state.live_stream_paused = not state.live_stream_paused
        st.rerun()
    if col2.button("Load last 100"):
        try:
            envelopes = client.replay_realtime_events(
                count=100,
                event_type=filters["event_types"] or None,
                workflow_id=filters["workflow_id"] or None,
                trace_id=filters["trace_id"] or None,
                agent_name=filters["agent_name"] or None,
            )
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.add_live_events(envelopes)
            st.rerun()
    if col3.button("Clear"):
        state.clear_live_events()
        st.rerun()
    try:
        active_subscriptions = len(client.list_realtime_subscriptions())
    except APIClientError:
        active_subscriptions = 0
    col4.metric("Active subscriptions", active_subscriptions)


def _render_event(envelope: dict[str, Any]) -> None:
    event = envelope["event"]
    category = _category_of(event["event_type"])
    icon = _CATEGORY_ICONS.get(category, "•")
    label = event["event_type"].replace("_", " ").title()
    correlation_bits = [
        f"{field}=`{event[field]}`"
        for field in ("workflow_id", "execution_id", "plan_id", "step_id", "trace_id", "agent_name", "tool_name", "user_id")
        if event.get(field)
    ]
    st.markdown(f"{icon} **{label}** — {event['timestamp']}")
    if correlation_bits:
        st.caption(" · ".join(correlation_bits))
    if event.get("data"):
        st.json(event["data"], expanded=False)


@st.fragment(run_every="2s")
def _live_feed(state: Any, client: APIClient, filters: dict[str, Any]) -> None:
    if not state.live_stream_paused:
        new_events = client.stream_realtime_events(
            event_type=filters["event_types"] or None,
            workflow_id=filters["workflow_id"] or None,
            trace_id=filters["trace_id"] or None,
            agent_name=filters["agent_name"] or None,
            listen_seconds=1.5,
        )
        if new_events:
            state.add_live_events(new_events)

    st.caption(("🟢 Live" if not state.live_stream_paused else "🟠 Paused") + f" — {len(state.live_events)} event(s) buffered.")
    for envelope in state.live_events[:50]:
        _render_event(envelope)


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Live",
    "Real-Time Event Streaming — watch workflows, agents, tools, approvals, AI calls, memory, "
    "reflections, plugins, and security events as they happen.",
)

if not state.is_authenticated:
    st.info("Log in on the **Settings** page first — the live event stream requires a valid access token.")
else:
    client = _authenticated_client(state)
    active_filters = _render_filters(state, client)
    st.divider()
    _render_controls(state, client, active_filters)
    st.divider()
    _live_feed(state, client, active_filters)
