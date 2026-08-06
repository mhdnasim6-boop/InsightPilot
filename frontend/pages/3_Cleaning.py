"""Cleaning page: run the default cleaning pipeline and review its report."""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error
from frontend.layouts import page_header, render_sidebar, require_dataset
from frontend.state import get_dashboard_state
from frontend.utils import format_number, format_percent

_RULE_LABELS = {
    "missing_value_rule": "Fill Missing Values",
    "duplicate_row_rule": "Remove Duplicate Rows",
    "whitespace_cleanup_rule": "Clean Up Whitespace",
    "data_type_normalization_rule": "Normalize Data Types",
    "column_name_normalization_rule": "Normalize Column Names",
}

state = get_dashboard_state()
render_sidebar(state)
page_header("Prepare", "Run the default cleaning pipeline and review what it found and fixed.", icon="🧹")

dataset = require_dataset(state)

if dataset is not None:
    st.caption(f"Active dataset: **{dataset['dataset_name']}** ({format_number(dataset['row_count'], 0)} rows)")

    if st.button("Run Cleaning Pipeline", type="primary"):
        client = APIClient(state.backend_url)
        new_outcome: dict[str, Any] | None
        with st.spinner("Cleaning dataset..."):
            try:
                new_outcome = client.clean_dataset(dataset["dataset_id"])
            except APIClientError as exc:
                render_api_error(exc)
                new_outcome = None

        if new_outcome is not None:
            state.current_cleaning_outcome = new_outcome
            state.selected_dataset = new_outcome["dataset"]
            state.current_analysis = None
            state.current_visualization = None
            state.add_activity(f"Cleaned dataset '{new_outcome['dataset']['dataset_name']}'.")
            st.success("Cleaning pipeline completed.")

    outcome = state.current_cleaning_outcome
    if outcome is not None:
        result = outcome["result"]
        st.divider()
        st.subheader("Cleaning Report")
        st.markdown(result.get("summary", ""))

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Rows", f"{result['rows_before']} → {result['rows_after']}")
        col2.metric("Columns", f"{result['columns_before']} → {result['columns_after']}")
        col3.metric("Duplicates Removed", format_number(result.get("duplicates_removed"), decimals=0))
        col4.metric("Quality Score", format_percent(result.get("quality_score", 0)))

        col5, col6 = st.columns(2)
        col5.metric("Missing Values Before", format_number(result.get("missing_values_before"), decimals=0))
        col6.metric("Missing Values After", format_number(result.get("missing_values_after"), decimals=0))

        if result.get("columns_modified"):
            st.caption(f"Columns modified: {', '.join(result['columns_modified'])}")

        st.subheader("Steps Applied")
        for step in result.get("steps_applied", []):
            label = _RULE_LABELS.get(step["rule_name"], step["rule_name"])
            with st.expander(f"{label} — {step['rows_before']} → {step['rows_after']} rows"):
                st.markdown(step.get("description", ""))
                if step.get("columns_affected"):
                    st.caption(f"Columns affected: {', '.join(step['columns_affected'])}")
                if step.get("details") and state.debug_mode:
                    st.json(step["details"])

        for warning in result.get("warnings", []):
            st.warning(warning)
