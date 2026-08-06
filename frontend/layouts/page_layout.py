"""Shared page chrome: sidebar navigation status, page headers, and dataset guard.

Every page in ``frontend/pages/`` calls :func:`render_sidebar` once near
the top of its script so the backend-status/selection chrome looks
identical everywhere — this is the one place that draws it.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError, APIError, BackendUnavailableError
from frontend.components.empty_state import render_empty_state
from frontend.components.warning_banner import render_api_error
from frontend.state import DashboardState


def render_sidebar(state: DashboardState) -> None:
    """Render the sidebar: branding, live backend status, and current selections.

    The real page nav above this (grouped: Dashboard/Data/Prepare/Analyze/
    Visualize/AI Copilot/Reports/Workflows/Settings, plus Advanced when
    enabled) is built by ``st.navigation()`` in ``frontend/app.py`` from
    ``frontend/navigation.py`` — this function only draws the chrome
    *below* that nav, identically on every page.
    """
    with st.sidebar:
        st.title("InsightPilot")
        st.caption("Agentic AI-powered Business Intelligence Assistant")
        st.divider()

        client = APIClient(state.backend_url)
        try:
            client.health_check()
            st.success(f"🟢 Backend connected\n\n{state.backend_url}")
        except BackendUnavailableError:
            st.error(f"🔴 Backend unreachable\n\n{state.backend_url}")
        except APIError as exc:
            st.warning(f"🟡 Backend error ({exc.status_code})\n\n{state.backend_url}")

        st.divider()
        st.subheader("Current Selection")
        dataset = state.selected_dataset
        st.caption(f"Dataset: {dataset['dataset_name'] if dataset else 'None selected'}")
        st.caption(f"Layout: {state.current_layout}")
        st.caption(f"Theme: {state.theme}")

        if state.recent_activity:
            st.divider()
            st.subheader("Recent Activity")
            for entry in state.recent_activity[:5]:
                st.caption(f"{entry['timestamp'][:19]} — {entry['message']}")


def page_header(title: str, subtitle: str | None = None, *, icon: str | None = None) -> None:
    """Render a consistent page title with an optional subtitle and icon.

    ``icon`` is optional and keyword-only, so every existing two-argument
    call site keeps working unchanged; pages adopt it incrementally.
    """
    st.title(f"{icon}  {title}" if icon else title)
    if subtitle:
        st.caption(subtitle)
    st.divider()


def require_dataset(state: DashboardState) -> dict[str, Any] | None:
    """Return the selected dataset, or render an empty state with a one-click way to
    pick one, and return ``None``."""
    dataset = state.selected_dataset
    if dataset is None:
        clicked = render_empty_state(
            "No dataset selected",
            "Upload a new file or pick a previously ingested one before using this page.",
            icon="📭",
            action_label="Go to Datasets",
            key="require_dataset_go_to_datasets",
        )
        if clicked:
            st.switch_page("pages/2_Datasets.py")
    return dataset


def ensure_session(state: DashboardState) -> str | None:
    """Return the current session_id, creating one via the backend on first use.

    Every page that calls the backend on the user's behalf (upload,
    cleaning, analysis, planning) needs a session_id first; centralizing
    that bootstrap here means each page calls one function instead of
    repeating the create-session try/except.
    """
    if state.session_id is not None:
        return state.session_id
    try:
        client = APIClient(state.backend_url)
        session = client.create_session()
        state.session_id = session["session_id"]
        return state.session_id
    except APIClientError as exc:
        render_api_error(exc)
        return None
