"""KPI dashboard: computed with SQL, no AI model involved."""
import pandas as pd
import plotly.express as px
import streamlit as st
from ui_common import current_dataset, page_setup

from insightpilot.data.kpis import compute_kpis

app = page_setup("Dashboard")
st.title("KPI Dashboard")
ds = current_dataset()
if not ds:
    st.info("Load a dataset on the Data page first.")
    st.stop()

meta = app.store.meta(ds)
try:
    k = compute_kpis(app.store, ds)
except Exception:  # noqa: BLE001
    st.error("I couldn't compute KPIs for this dataset. Check that it has numeric revenue-like columns.")
    st.stop()

if not (meta.get("cleaned") or meta.get("cleaning_reviewed")):
    st.warning("This data has not been cleaned yet, so duplicates or invalid rows may distort the figures. Clean it on the Data page.")
v = k["kpis"]
cols = st.columns(4)
if v.get("revenue") is not None:
    cols[0].metric("Revenue", f"{v['revenue']:,.0f}")
if v.get("profit") is not None:
    cols[1].metric("Profit", f"{v['profit']:,.0f}")
if v.get("margin_pct") is not None:
    cols[2].metric("Margin", f"{v['margin_pct']:.1f}%")
cols[3].metric("Records", f"{v['records']:,}")

m = k.get("monthly")
if m and m.get("rows"):
    df = pd.DataFrame(m["rows"], columns=m["columns"])
    st.plotly_chart(px.line(df, x=df.columns[0], y=df.columns[1], markers=True, title="Monthly trend"), use_container_width=True)
left, right = st.columns(2)
for slot, key, title in ((left, "by_region", "By region"), (right, "by_category", "By category")):
    r = k.get(key)
    if r and r.get("rows"):
        df = pd.DataFrame(r["rows"], columns=r["columns"])
        slot.plotly_chart(px.bar(df, x=df.columns[0], y=df.columns[1], title=title), use_container_width=True)
st.caption("All figures are calculated by DuckDB SQL queries on the current version of the dataset.")
