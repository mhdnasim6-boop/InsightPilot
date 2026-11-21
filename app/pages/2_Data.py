"""Upload, preview and clean data (cleaning needs human approval)."""
import pandas as pd
import streamlit as st
from ui_common import cleaning_approval_ui, current_dataset, load_sample, page_setup

from insightpilot.data.store import DatasetError

app = page_setup("Data")
st.title("Data")

up = st.file_uploader("Upload a CSV or Excel file", type=["csv", "xlsx", "xls"])
if up is not None and st.session_state.get("last_upload") != (up.name, up.size):
    try:
        st.session_state["dataset_id"] = app.upload_dataset(up.name, up.getvalue())
        st.session_state["last_upload"] = (up.name, up.size)
        st.rerun()
    except DatasetError as exc:
        st.error(str(exc))
if st.button("Load sample sales data"):
    load_sample(app)
    st.rerun()

ds = current_dataset()
if not ds:
    st.stop()
meta = app.store.meta(ds)
st.subheader(meta["filename"])
st.caption(f"{meta['rows']:,} rows - {'cleaned' if meta.get('cleaned') else 'not cleaned yet'}")
st.dataframe(app.store.load_df(ds).head(50), use_container_width=True)

st.subheader("Data cleaning")
tkey = f"clean_thread_{ds}"
if tkey not in st.session_state:
    st.session_state[tkey] = app.new_conversation(ds, "Data cleaning")
tid = st.session_state[tkey]


def handle(result: dict) -> None:
    if result["status"] == "error":
        st.error(result["error"])
    elif result["status"] == "done":
        st.success(result["answer"])
        st.session_state.pop(f"pending_{tid}", None)
    else:
        st.session_state[f"pending_{tid}"] = result["interrupt"]


if st.button("Check data quality", type="primary"):
    with st.spinner("Cleaning agent is checking the data..."):
        handle(app.start_cleaning(tid, ds))
    st.rerun()

pending = st.session_state.get(f"pending_{tid}") or app.pending_interrupt(tid)
if pending and pending.get("type") == "cleaning_fixes":
    decision = cleaning_approval_ui(pending, f"clean_{tid}")
    if decision is not None:
        with st.spinner("Applying approved fixes..."):
            result = app.resume(tid, decision)
        st.session_state.pop(f"pending_{tid}", None)
        handle(result)
        st.rerun()

log = meta.get("cleaning_log")
if log:
    st.subheader("What was changed")
    st.dataframe(pd.DataFrame(log)[[c for c in ("message", "rows_before", "rows_after", "status") if c in pd.DataFrame(log).columns]],
                 use_container_width=True, hide_index=True)
