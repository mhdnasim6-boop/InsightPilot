"""The AI Copilot: conversation memory + Human-in-the-Loop approvals."""
import streamlit as st
from ui_common import cleaning_approval_ui, current_dataset, email_approval_ui, page_setup, render_result

app = page_setup("Copilot")
st.title("AI Copilot")
ds = current_dataset()
if not ds:
    st.info("Load a dataset on the Data page first.")
    st.stop()

convs = [c for c in app.list_conversations(ds) if c["title"] != "Data cleaning"]
with st.sidebar:
    if st.button("New conversation"):
        st.session_state["thread_id"] = app.new_conversation(ds)
        st.rerun()
    if convs:
        ids = [c["thread_id"] for c in convs]
        titles = {c["thread_id"]: c["title"] for c in convs}
        cur = st.session_state.get("thread_id")
        st.session_state["thread_id"] = st.radio("Conversations", ids, index=ids.index(cur) if cur in ids else 0,
                                                 format_func=lambda i: titles[i])
if not st.session_state.get("thread_id") or st.session_state.get("thread_id") not in {c["thread_id"] for c in convs}:
    st.session_state["thread_id"] = convs[0]["thread_id"] if convs else app.new_conversation(ds)
tid = st.session_state["thread_id"]
last = st.session_state.setdefault("last_results", {})

hist = app.history(tid)
for i, m in enumerate(hist):
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m["role"] == "assistant" and i == len(hist) - 1 and tid in last:
            render_result(last[tid])
if not hist:
    st.caption("Try: *Which region has the highest revenue?*  -  *Why did North electronics revenue drop in March 2025?*  -  "
               "*Make a report on revenue by region and email it to name@company.com*")


def handle(result: dict) -> None:
    if result["status"] == "error":
        st.error(result["error"])
    elif result["status"] == "done":
        last[tid] = result


pending = app.pending_interrupt(tid)
if pending:
    decision = None
    if pending["type"] == "cleaning_fixes":
        decision = cleaning_approval_ui(pending, f"cp_clean_{tid}")
    elif pending["type"] == "send_email":
        decision = email_approval_ui(pending, f"cp_mail_{tid}")
    if decision is not None:
        with st.spinner("Continuing..."):
            handle(app.resume(tid, decision))
        st.rerun()
else:
    q = st.chat_input("Ask a question about your data")
    if q:
        with st.chat_message("user"):
            st.markdown(q)
        with st.spinner("Agents are working..."):
            handle(app.ask(tid, ds, q))
        st.rerun()
