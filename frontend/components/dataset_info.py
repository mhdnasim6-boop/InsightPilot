"""Dataset info component: renders a BusinessDataset's shape and column metadata."""

from typing import Any

import streamlit as st

from frontend.utils.formatting import format_bytes, format_number, format_timestamp


def render_dataset_info(dataset: dict[str, Any]) -> None:
    """Render a BusinessDataset's summary metrics and per-column metadata table."""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rows", format_number(dataset.get("row_count"), decimals=0))
    col2.metric("Columns", format_number(dataset.get("column_count"), decimals=0))
    col3.metric("File Size", format_bytes(dataset.get("file_size")))
    col4.metric("Loaded At", format_timestamp(dataset.get("loaded_at")))

    columns = dataset.get("columns") or []
    if not columns:
        st.caption("No column metadata available.")
        return

    st.dataframe(
        [
            {
                "Column": column.get("name"),
                "Type": column.get("dtype"),
                "Non-Null": column.get("non_null_count"),
                "Null": column.get("null_count"),
                "Unique": column.get("unique_count"),
            }
            for column in columns
        ],
        width="stretch",
        hide_index=True,
    )
