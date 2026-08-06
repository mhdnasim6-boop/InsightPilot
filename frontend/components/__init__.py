"""Reusable Streamlit UI components shared across dashboard pages.

Every component here is a pure rendering function: it takes plain
``dict``/``list`` data (already fetched by a page through the API client)
and calls Streamlit primitives. None of them fetch data, mutate session
state, or make a decision about what the data means — that keeps them
reusable by future chatbot/report modules that display the same backend
payloads through a different surface.
"""

from frontend.components.chart_container import (
    render_chart,
    render_chart_grid,
    render_layout,
)
from frontend.components.dataset_info import render_dataset_info
from frontend.components.empty_state import render_empty_state
from frontend.components.execution_plan_viewer import (
    render_execution_plan,
    render_plan_steps,
)
from frontend.components.insight_card import render_insight_cards
from frontend.components.kpi_card import render_kpi_cards
from frontend.components.loading_indicator import loading
from frontend.components.status_badge import (
    render_status_badge,
    status_label,
    status_tone,
)
from frontend.components.warning_banner import render_api_error, render_banner

__all__ = [
    "loading",
    "render_api_error",
    "render_banner",
    "render_chart",
    "render_chart_grid",
    "render_dataset_info",
    "render_empty_state",
    "render_execution_plan",
    "render_insight_cards",
    "render_kpi_cards",
    "render_layout",
    "render_plan_steps",
    "render_status_badge",
    "status_label",
    "status_tone",
]
