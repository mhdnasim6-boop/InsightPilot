"""Memory page: browse, search, and manage the long-term knowledge layer every
agent/service writes into automatically (datasets, analyses, visualizations,
reports, executive summaries, executions, approvals, plans/decisions,
conversation turns, external research, and user preferences).

Read/manage only — no memory-writing controls here; every memory shown
was created automatically by whichever service produced it
(``MemoryService.remember()``), exactly like the Observability page
never lets you hand-craft a trace.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state

_TYPE_OPTIONS = [
    "conversation",
    "dataset",
    "analysis",
    "visualization",
    "report",
    "execution",
    "approval",
    "user_preference",
    "decision",
    "external_knowledge",
]
_SCOPE_OPTIONS = ["session", "user", "project", "global"]


def _render_statistics(client: APIClient) -> None:
    st.subheader("Statistics")
    try:
        stats = client.get_memory_statistics()
    except APIClientError as exc:
        render_api_error(exc)
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total memories", stats["total_items"])
    col2.metric("Recent (24h)", stats["recent_activity_count"])
    col3.metric("Avg. importance", f"{stats['average_importance']:.2f}")
    col4.metric("Types in use", len(stats["by_type"]))

    if stats["by_type"]:
        st.caption("By type: " + ", ".join(f"{k} ({v})" for k, v in stats["by_type"].items()))
    if stats["by_scope"]:
        st.caption("By scope: " + ", ".join(f"{k} ({v})" for k, v in stats["by_scope"].items()))


def _render_explorer(client: APIClient, state: Any) -> list[dict[str, Any]]:
    st.subheader("Memory Explorer")
    col1, col2, col3 = st.columns(3)
    keyword = col1.text_input("Keyword")
    memory_type = col2.selectbox("Type", ["(any)", *_TYPE_OPTIONS])
    scope = col3.selectbox("Scope", ["(any)", *_SCOPE_OPTIONS])

    col4, col5 = st.columns(2)
    tags_raw = col4.text_input("Tags (comma-separated)")
    min_importance = col5.slider("Minimum importance", 0.0, 1.0, 0.0, 0.05)

    tags = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]

    try:
        if keyword or tags or memory_type != "(any)" or scope != "(any)" or min_importance > 0.0:
            result = client.search_memories(
                keyword=keyword or None,
                tags=tags or None,
                memory_type=None if memory_type == "(any)" else memory_type,
                scope=None if scope == "(any)" else scope,
                min_importance=min_importance or None,
                top_k=50,
            )
            items = result["items"]
            st.caption(f"{result['total_matched']} match(es) — showing up to 50.")
        else:
            items = client.list_memories()
    except APIClientError as exc:
        render_api_error(exc)
        return []

    if not items:
        st.info("No memories found.")
        return []

    st.dataframe(
        [
            {
                "Title": item["title"],
                "Type": item["memory_type"],
                "Scope": item["scope"],
                "Importance": round(item["importance"], 2),
                "Tags": ", ".join(item["tags"]) or "—",
                "Created": item["created_at"],
            }
            for item in items
        ],
        width="stretch",
        hide_index=True,
    )
    return items


def _render_details_and_actions(items: list[dict[str, Any]], client: APIClient, state: Any) -> None:
    if not items:
        return
    st.subheader("Memory Details")
    options = {f"{item['title']} ({item['memory_type']})": item["memory_id"] for item in items}
    chosen_label = st.selectbox("Select a memory", list(options.keys()))
    memory_id = options[chosen_label]

    try:
        memory = client.get_memory(memory_id)
    except APIClientError as exc:
        render_api_error(exc)
        return

    with st.container(border=True):
        st.markdown(f"**{memory['title']}**")
        st.caption(memory["summary"])
        st.json(memory["content"], expanded=False)
        if memory["references"]:
            st.markdown(
                "References: "
                + ", ".join(f"{r['reference_type']}:{r['reference_id']}" for r in memory["references"])
            )
        if st.button("Delete this memory", key=f"delete_{memory_id}"):
            try:
                client.delete_memory(memory_id)
            except APIClientError as exc:
                render_api_error(exc)
            else:
                state.add_activity(f"Deleted memory '{memory['title']}'.")
                st.rerun()


def _render_summary(client: APIClient) -> None:
    with st.expander("Summarize all memories"):
        if st.button("Generate summary"):
            try:
                summary = client.summarize_memories()
            except APIClientError as exc:
                render_api_error(exc)
            else:
                st.text(summary)


def _render_management(client: APIClient, state: Any) -> None:
    st.subheader("Export & Cleanup")
    col1, col2, col3 = st.columns(3)

    if col1.button("Export JSON"):
        try:
            content = client.export_memories("json")
        except APIClientError as exc:
            render_api_error(exc)
        else:
            st.download_button("Download JSON", content, file_name="memories.json", key="memory_export_json")

    if col2.button("Export Markdown"):
        try:
            content = client.export_memories("markdown")
        except APIClientError as exc:
            render_api_error(exc)
        else:
            st.download_button("Download Markdown", content, file_name="memories.md", key="memory_export_md")

    if col3.button("Clear all memories", type="secondary"):
        try:
            client.clear_memories()
        except APIClientError as exc:
            render_api_error(exc)
        else:
            state.add_activity("Cleared all memories.")
            st.rerun()


state = get_dashboard_state()
render_sidebar(state)
page_header(
    "Memory",
    "The long-term knowledge layer every agent writes into automatically — datasets, "
    "analyses, reports, executions, approvals, plans, conversations, and external research.",
)

client = APIClient(state.backend_url)

_render_statistics(client)
st.divider()
items = _render_explorer(client, state)
_render_details_and_actions(items, client, state)
st.divider()
_render_summary(client)
_render_management(client, state)
