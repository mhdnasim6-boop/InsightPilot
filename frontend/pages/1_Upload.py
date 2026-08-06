"""Upload page: upload a CSV/Excel file and ingest it into a BusinessDataset."""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError, APIError
from frontend.components import render_api_error, render_banner, render_dataset_info
from frontend.layouts import ensure_session, page_header, render_sidebar
from frontend.state import DashboardState, get_dashboard_state


def _render_validation_summary(dataset: dict[str, Any]) -> None:
    quality = dataset.get("quality_summary") or {}
    if not quality:
        return
    st.subheader("Validation Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Errors", quality.get("error_count", 0))
    col2.metric("Warnings", quality.get("warning_count", 0))
    col3.metric("Missing Values", f"{quality.get('missing_value_percentage', 0)}%")
    if quality.get("is_valid"):
        render_banner("Dataset passed validation.", "success")
    else:
        render_banner("Dataset was ingested but failed strict validation checks.", "warning")


def _render_validation_issues(error: APIError) -> None:
    issues = error.detail.get("issues") if isinstance(error.detail, dict) else None
    if not issues:
        return
    st.subheader("Validation Issues")
    for issue in issues:
        message = f"[{issue.get('code')}] {issue.get('message')}"
        if issue.get("severity") == "error":
            render_banner(message, "error")
        else:
            render_banner(message, "warning")


def _upload_and_ingest(client: APIClient, session_id: str, uploaded_file: Any, state: DashboardState) -> None:
    status = st.status("Uploading and ingesting dataset...", expanded=True)
    try:
        dataset = client.upload_dataset(
            session_id=session_id,
            filename=uploaded_file.name,
            content=uploaded_file.getvalue(),
            content_type=uploaded_file.type,
        )
    except APIError as exc:
        status.update(label="Ingestion failed.", state="error", expanded=True)
        render_api_error(exc)
        _render_validation_issues(exc)
        return
    except APIClientError as exc:
        status.update(label="Ingestion failed.", state="error", expanded=True)
        render_api_error(exc)
        return

    status.update(label=f"Ingested '{dataset['dataset_name']}'.", state="complete", expanded=False)

    state.selected_dataset = dataset
    state.current_analysis = None
    state.current_visualization = None
    state.add_activity(f"Uploaded and ingested '{dataset['dataset_name']}'.")

    st.success(f"Dataset '{dataset['dataset_name']}' ingested successfully.")
    render_dataset_info(dataset)
    _render_validation_summary(dataset)


state = get_dashboard_state()
render_sidebar(state)
page_header("Upload Data", "Upload a CSV or Excel file to get started.", icon="⬆️")

session_id = ensure_session(state)
uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    if session_id is None:
        render_banner("Cannot upload: no active session and the backend is unreachable.", "error")
    elif st.button("Upload & Ingest", type="primary"):
        _upload_and_ingest(APIClient(state.backend_url), session_id, uploaded_file, state)
