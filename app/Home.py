"""InsightPilot home page."""
import streamlit as st
from ui_common import current_dataset, load_sample, page_setup

app = page_setup("Home")
st.title("📊 InsightPilot")
st.subheader("An agentic business-intelligence copilot")
st.write("Upload business data, let the agents clean it (with your approval), then ask questions in plain English. "
         "Numbers are calculated by a SQL engine, never guessed by the AI model.")

c1, c2, c3 = st.columns(3)
c1.markdown("**1. Data**  \nUpload a CSV or Excel file, review and approve the proposed cleaning fixes.")
c2.markdown("**2. Dashboard**  \nSee revenue, profit and trends instantly.")
c3.markdown("**3. Copilot**  \nAsk questions, get charts, research context, a PDF report and an approved email.")

st.divider()
if current_dataset() is None:
    st.write("No data yet. Try the built-in demo dataset (2,000 sales orders with planted data issues):")
    if st.button("Load sample sales data", type="primary"):
        load_sample(app)
        st.rerun()
else:
    st.success("A dataset is loaded. Open **Data** to clean it, **Dashboard** for KPIs, or **Copilot** to ask questions.")
st.caption("Agents: Supervisor, Data Cleaning, Data Analyst, Visualization, Research, Report & Email.")
