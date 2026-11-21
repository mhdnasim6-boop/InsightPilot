"""Shared Streamlit helpers: app singleton, sidebar, and the two Human-in-the-Loop approval widgets."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import plotly.io as pio  # noqa: E402
import streamlit as st  # noqa: E402

from insightpilot.config import get_settings  # noqa: E402
from insightpilot.runtime import InsightPilotApp  # noqa: E402

SAMPLE = ROOT / "sample_data" / "sales.csv"


@st.cache_resource(show_spinner=False)
def get_app() -> InsightPilotApp:
    return InsightPilotApp(get_settings())


def page_setup(title: str) -> InsightPilotApp:
    st.set_page_config(page_title=f"InsightPilot - {title}", page_icon="📊", layout="wide")
    app = get_app()
    with st.sidebar:
        st.markdown("### InsightPilot")
        st.caption(f"AI backend: **{app.provider.describe()}**  \nSwitch with `LLM_PROVIDER` in `.env`.")
        datasets = app.store.list_datasets()
        if datasets:
            ids = [d["id"] for d in datasets]
            names = {d["id"]: f"{d['filename']} ({d['rows']:,} rows)" for d in datasets}
            current = st.session_state.get("dataset_id")
            idx = ids.index(current) if current in ids else 0
            st.session_state["dataset_id"] = st.selectbox("Dataset", ids, index=idx, format_func=lambda i: names[i])
        else:
            st.session_state["dataset_id"] = None
            st.info("No dataset yet. Upload one on the Data page.")
    return app


def current_dataset() -> str | None:
    return st.session_state.get("dataset_id")


def load_sample(app: InsightPilotApp) -> str:
    ds = app.upload_dataset("sales.csv", SAMPLE.read_bytes())
    st.session_state["dataset_id"] = ds
    return ds


def show_figure(fig_json: str) -> None:
    if fig_json:
        st.plotly_chart(pio.from_json(fig_json), use_container_width=True)


def show_table(res: dict) -> None:
    if res and res.get("rows"):
        st.dataframe(pd.DataFrame(res["rows"], columns=res["columns"]), use_container_width=True, hide_index=True)


def cleaning_approval_ui(payload: dict, key: str) -> dict | None:
    """Show proposed fixes with checkboxes. Returns the decision dict once the user submits, else None."""
    st.warning("**Approval needed: data cleaning.** Nothing has been changed yet. Choose which fixes to apply.")
    chosen = []
    for f in payload["fixes"]:
        label = f"{f['reason']}  \n*{f['op'].replace('_', ' ')}"
        label += f" on `{f['column']}`" if f.get("column") else ""
        label += f" - affects {f['affected_rows']:,} rows*"
        if f.get("unparseable"):
            label += f" ({f['unparseable']} values cannot be converted)"
        if st.checkbox(label, value=True, key=f"{key}_{f['id']}"):
            chosen.append(f["id"])
    c1, c2 = st.columns(2)
    if c1.button(f"Apply {len(chosen)} selected fix(es)", type="primary", key=f"{key}_apply"):
        return {"approved_ids": chosen}
    if c2.button("Skip cleaning", key=f"{key}_skip"):
        return {"approved_ids": []}
    return None


def email_approval_ui(payload: dict, key: str) -> dict | None:
    """Show the drafted email for review/editing. Nothing is sent until Approve is pressed."""
    d = payload["draft"]
    st.warning("**Approval needed: send email.** Review the draft. It is only sent if you approve.")
    to = st.text_input("To", d["to"], key=f"{key}_to")
    subject = st.text_input("Subject", d["subject"], key=f"{key}_subject")
    body = st.text_area("Body", d["body"], height=200, key=f"{key}_body")
    st.caption("Attachment: " + Path(d["attachment"]).name if d.get("attachment") else "No attachment")
    c1, c2 = st.columns(2)
    if c1.button("Approve and send", type="primary", key=f"{key}_send"):
        return {"approved": True, "to": to, "subject": subject, "body": body}
    if c2.button("Reject", key=f"{key}_reject"):
        return {"approved": False}
    return None


def render_result(result: dict) -> None:
    """Everything below an assistant answer: chart, table, report download, agent activity."""
    show_figure(result.get("visualization", ""))
    res = result.get("analysis_result")
    if res:
        with st.expander("Result table and SQL"):
            show_table(res)
            st.code(res.get("sql", ""), language="sql")
    rp = result.get("report")
    if rp and Path(rp["path"]).is_file():
        st.download_button("Download PDF report", Path(rp["path"]).read_bytes(), file_name=Path(rp["path"]).name,
                           mime="application/pdf", key=f"dl_{rp['path']}")
    if result.get("audit"):
        with st.expander("Agent activity"):
            for a in result["audit"]:
                st.write(f"`{a['ts'][11:]}` **{a['agent']}** - {a['status']}: {a['detail']}")
