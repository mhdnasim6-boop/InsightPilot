"""Datasets page: list every ingested dataset and select one for downstream pages."""

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error, render_dataset_info
from frontend.layouts import page_header, render_sidebar
from frontend.state import get_dashboard_state
from frontend.utils import format_number, format_timestamp

state = get_dashboard_state()
render_sidebar(state)
page_header("My Datasets", "Select a previously uploaded dataset to work with.", icon="📂")

client = APIClient(state.backend_url)

try:
    datasets = client.list_datasets()
except APIClientError as exc:
    render_api_error(exc)
    datasets = []

if not datasets:
    st.info("No datasets ingested yet. Visit the Upload page to add one.")
else:
    st.dataframe(
        [
            {
                "Dataset ID": dataset["dataset_id"],
                "Name": dataset["dataset_name"],
                "Rows": format_number(dataset["row_count"], decimals=0),
                "Columns": format_number(dataset["column_count"], decimals=0),
                "Loaded At": format_timestamp(dataset.get("loaded_at")),
            }
            for dataset in datasets
        ],
        width="stretch",
        hide_index=True,
    )

    options = {f"{dataset['dataset_name']} ({dataset['dataset_id'][:8]})": dataset for dataset in datasets}
    current_id = state.selected_dataset["dataset_id"] if state.selected_dataset else None
    labels = list(options.keys())
    default_index = next(
        (i for i, dataset in enumerate(options.values()) if dataset["dataset_id"] == current_id), 0
    )

    chosen_label = st.selectbox("Select a dataset", labels, index=default_index)
    chosen_dataset = options[chosen_label]

    if st.button("Use this dataset", type="primary"):
        if state.selected_dataset is None or state.selected_dataset["dataset_id"] != chosen_dataset["dataset_id"]:
            state.current_analysis = None
            state.current_visualization = None
        state.selected_dataset = chosen_dataset
        state.add_activity(f"Selected dataset '{chosen_dataset['dataset_name']}'.")
        st.success(f"'{chosen_dataset['dataset_name']}' is now the active dataset.")

    if state.selected_dataset is not None:
        st.divider()
        st.subheader(f"Active Dataset: {state.selected_dataset['dataset_name']}")
        render_dataset_info(state.selected_dataset)
