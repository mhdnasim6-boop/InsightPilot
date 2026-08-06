"""InsightPilot Streamlit frontend — entrypoint.

A thin launcher only: it builds the grouped sidebar nav tree (see
``frontend/navigation.py``) and hands off to ``st.navigation()`` — no
page content lives here (that moved to ``frontend/pages/0_Dashboard.py``,
Phase v1.0 navigation redesign). Every page under ``frontend/pages/``
still calls :func:`frontend.layouts.render_sidebar` itself; this module
only decides *which* pages are offered, driven by
``state.advanced_mode``.

Run with: ``uv run streamlit run frontend/app.py``
"""

import streamlit as st

from config.settings import get_settings
from frontend.navigation import build_navigation
from frontend.state import get_dashboard_state
from shared.logging import setup_logging

settings = get_settings()
setup_logging(log_level=settings.log_level)

st.set_page_config(page_title=settings.app_name, layout="wide")

state = get_dashboard_state()
nav = build_navigation(state.advanced_mode)
st.navigation(nav, position="sidebar").run()
