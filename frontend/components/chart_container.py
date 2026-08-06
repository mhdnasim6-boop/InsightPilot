"""Chart container component: renders server-rendered Plotly figures inside a layout grid.

Every figure is built from JSON the backend already produced via
``PlotlyExporter`` (``fig.to_json()`` on the server, ``go.Figure(json)``
here) — this module never computes a trace, an axis, or a color; it only
arranges already-finished figures on the page. ``theme=None`` is passed to
``st.plotly_chart`` deliberately: the figure already carries the colors
from the backend's ``ThemeRegistry`` selection, and Streamlit's own
default theming would otherwise override them.
"""

from typing import Any

import plotly.graph_objects as go
import streamlit as st


def render_chart(chart_spec: dict[str, Any], figure_json: dict[str, Any], *, key: str | None = None) -> None:
    """Render one chart from its ChartSpecification and pre-rendered Plotly figure JSON."""
    if chart_spec.get("description"):
        st.caption(chart_spec["description"])
    figure = go.Figure(figure_json)
    st.plotly_chart(figure, theme=None, width="stretch", key=key)


def render_chart_grid(
    charts: list[dict[str, Any]], rendered_charts: dict[str, dict[str, Any]], *, columns: int = 2
) -> None:
    """Render a list of charts in a grid, ``columns`` charts per row."""
    if not charts:
        st.info("No charts to display.")
        return

    rows = [charts[i : i + columns] for i in range(0, len(charts), columns)]
    for row_index, row in enumerate(rows):
        cols = st.columns(columns)
        for col_index, (col, chart) in enumerate(zip(cols, row, strict=False)):
            with col:
                st.markdown(f"**{chart.get('title', 'Chart')}**")
                figure_json = rendered_charts.get(chart["chart_id"])
                if figure_json is None:
                    st.warning(f"No rendered figure for chart '{chart.get('chart_id')}'.")
                    continue
                render_chart(chart, figure_json, key=f"chart_{row_index}_{col_index}_{chart['chart_id']}")


def render_layout(
    layout: dict[str, Any], charts: list[dict[str, Any]], rendered_charts: dict[str, dict[str, Any]]
) -> None:
    """Render every section of a Layout, each as a header followed by its own chart grid."""
    charts_by_id = {chart["chart_id"]: chart for chart in charts}
    for section in layout.get("sections", []):
        st.subheader(section.get("title", "Section"))
        section_charts = [charts_by_id[cid] for cid in section.get("chart_ids", []) if cid in charts_by_id]
        render_chart_grid(section_charts, rendered_charts, columns=section.get("columns", 2))
