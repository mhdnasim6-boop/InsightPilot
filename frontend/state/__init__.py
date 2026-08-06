"""Reusable dashboard session state — no business logic, only storage."""

from frontend.state.session_state import DashboardState, get_dashboard_state

__all__ = ["DashboardState", "get_dashboard_state"]
