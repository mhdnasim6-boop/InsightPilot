"""Visualization page: recommended charts, layout sections, theme switching,
chart filtering, and JSON export.
"""

import json
from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error, render_chart_grid, render_layout
from frontend.layouts import page_header, render_sidebar, require_dataset
from frontend.state import get_dashboard_state

LAYOUT_TYPES = ["executive_summary", "detailed_analysis", "kpi_dashboard", "comparison_dashboard"]
_LAYOUT_LABELS = {
    "executive_summary": "Executive Summary", "detailed_analysis": "Detailed Analysis",
    "kpi_dashboard": "KPI Dashboard", "comparison_dashboard": "Comparison Dashboard",
}
THEMES = ["light", "dark", "corporate"]

state = get_dashboard_state()
render_sidebar(state)
page_header("Visualize", "Executive dashboards, recommended charts, and interactive exploration.", icon="📈")

dataset = require_dataset(state)

if dataset is not None:
    analysis = state.current_analysis
    analysis_matches = analysis is not None and analysis.get("dataset_id") == dataset["dataset_id"]

    if not analysis_matches:
        st.warning("No analysis available for this dataset yet. Run Analysis first, then return here.")
    else:
        assert analysis is not None  # guaranteed by analysis_matches

        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            st.selectbox(
                "Layout", LAYOUT_TYPES, key="dashboard_current_layout",
                format_func=lambda value: _LAYOUT_LABELS.get(value, value),
            )
        with col2:
            st.selectbox("Theme", THEMES, key="dashboard_theme")
        with col3:
            st.write("")
            generate = st.button("Generate", type="primary")

        if generate:
            client = APIClient(state.backend_url)
            new_visualization: dict[str, Any] | None
            with st.spinner("Generating visualizations..."):
                try:
                    new_visualization = client.generate_visualizations(
                        analysis_result=analysis,
                        dataset=dataset,
                        layout_type=state.current_layout,
                        theme=state.theme,
                    )
                except APIClientError as exc:
                    render_api_error(exc)
                    new_visualization = None

            if new_visualization is not None:
                state.current_visualization = new_visualization
                state.add_activity(f"Generated visualizations for '{dataset['dataset_name']}'.")

        visualization = state.current_visualization
        if visualization is not None:
            result = visualization["visualization_result"]
            rendered_charts = visualization["rendered_charts"]
            charts = result["charts"]

            for recommendation in result.get("recommendations", []):
                st.info(recommendation)
            for warning in result.get("warnings", []):
                st.warning(warning)

            available_types = sorted({chart["chart_type"] for chart in charts})
            selected_types = st.multiselect("Filter by chart type", available_types, default=available_types)
            state.selected_charts = selected_types

            filtered_charts = [chart for chart in charts if chart["chart_type"] in selected_types]

            st.divider()
            if set(selected_types) == set(available_types):
                render_layout(result["layout"], filtered_charts, rendered_charts)
            else:
                render_chart_grid(filtered_charts, rendered_charts)

            st.divider()
            st.subheader("Export (JSON)")
            st.download_button(
                "Download full visualization result",
                data=json.dumps(visualization, indent=2),
                file_name=f"{dataset['dataset_name']}_visualization.json",
                mime="application/json",
            )
            for chart in filtered_charts:
                figure_json = rendered_charts.get(chart["chart_id"])
                if figure_json is not None:
                    st.download_button(
                        f"Download '{chart['title']}' (JSON)",
                        data=json.dumps(figure_json, indent=2),
                        file_name=f"{chart['chart_id']}.json",
                        mime="application/json",
                        key=f"export_{chart['chart_id']}",
                    )
