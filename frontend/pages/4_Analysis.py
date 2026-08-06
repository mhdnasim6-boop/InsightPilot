"""Analysis page: run and display AnalysisResult — summary, KPIs, statistics,
trends, correlations, anomalies, and business insights.
"""

from typing import Any

import streamlit as st

from frontend.api import APIClient, APIClientError
from frontend.components import render_api_error, render_insight_cards, render_kpi_cards
from frontend.layouts import page_header, render_sidebar, require_dataset
from frontend.state import get_dashboard_state
from frontend.utils import format_number, format_percent


def _render_summary(summary: dict[str, Any]) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Rows", format_number(summary.get("row_count"), decimals=0))
    col2.metric("Columns", format_number(summary.get("column_count"), decimals=0))
    col3.metric("Missing Values", format_number(summary.get("missing_values"), decimals=0))
    col4.metric("Duplicate Rows", format_number(summary.get("duplicate_count"), decimals=0))

    st.caption(f"Numeric columns: {', '.join(summary.get('numeric_columns', [])) or 'none'}")
    st.caption(f"Categorical columns: {', '.join(summary.get('categorical_columns', [])) or 'none'}")


def _render_statistics(statistics: dict[str, Any]) -> None:
    columns = statistics.get("columns", {})
    if not columns:
        st.info("No numeric columns to describe.")
        return
    st.dataframe(
        [
            {
                "Column": name,
                "Mean": format_number(stats.get("mean")),
                "Median": format_number(stats.get("median")),
                "Std Dev": format_number(stats.get("std")),
                "Min": format_number(stats.get("minimum")),
                "Max": format_number(stats.get("maximum")),
            }
            for name, stats in columns.items()
        ],
        width="stretch",
        hide_index=True,
    )
    for name, stats in columns.items():
        with st.expander(f"{name} — full distribution"):
            st.json(
                {
                    "quartiles": stats.get("quartiles"),
                    "percentiles": stats.get("percentiles"),
                    "distribution_summary": stats.get("distribution_summary"),
                    "mode": stats.get("mode"),
                }
            )


def _render_trends(trends: dict[str, Any]) -> None:
    if not trends.get("applicable", True):
        st.info(trends.get("reason") or "Trend analysis is not applicable to this dataset.")
        return
    st.caption(f"Time column: `{trends.get('time_column')}` — rolling window: {trends.get('window')}")
    for series in trends.get("series", []):
        st.markdown(f"**{series['column']}** — growth rate: {format_percent(series.get('growth_rate'))}")
        rolling = [value for value in series.get("rolling_average", []) if value is not None]
        if rolling:
            st.line_chart(rolling)


def _render_correlations(correlations: dict[str, Any]) -> None:
    if not correlations.get("applicable", True):
        st.info(correlations.get("reason") or "Correlation analysis is not applicable to this dataset.")
        return
    columns = correlations.get("columns", [])
    pearson = correlations.get("pearson_matrix", {})
    if columns and pearson:
        st.markdown("**Pearson correlation matrix**")
        rows = [
            {"Column": row, **{col: format_number(pearson.get(row, {}).get(col)) for col in columns}}
            for row in columns
        ]
        st.dataframe(rows, width="stretch", hide_index=True)

    correlation_groups = (
        ("Strong Positive", correlations.get("strong_positive", [])),
        ("Strong Negative", correlations.get("strong_negative", [])),
    )
    for label, pairs in correlation_groups:
        if pairs:
            st.markdown(f"**{label} Correlations**")
            pair_rows = [
                {
                    "Column A": pair["column_a"],
                    "Column B": pair["column_b"],
                    "Pearson": format_number(pair.get("pearson")),
                }
                for pair in pairs
            ]
            st.dataframe(
                pair_rows,
                width="stretch",
                hide_index=True,
            )


def _render_anomalies(anomalies: dict[str, Any]) -> None:
    if not anomalies.get("applicable", True):
        st.info(anomalies.get("reason") or "Anomaly detection is not applicable to this dataset.")
        return
    columns = anomalies.get("columns", [])
    if not columns:
        st.info("No anomalies detected.")
    else:
        st.dataframe(
            [
                {
                    "Column": column["column"],
                    "Z-Score Outliers": column.get("zscore_outlier_count", 0),
                    "Z-Score %": format_percent(column.get("zscore_outlier_percentage")),
                    "IQR Outliers": column.get("iqr_outlier_count", 0),
                    "IQR %": format_percent(column.get("iqr_outlier_percentage")),
                }
                for column in columns
            ],
            width="stretch",
            hide_index=True,
        )
    isolation_forest = anomalies.get("isolation_forest") or {}
    if isolation_forest.get("note"):
        st.caption(isolation_forest["note"])


state = get_dashboard_state()
render_sidebar(state)
page_header("Analysis", "KPIs, statistics, trends, correlations, anomalies, and business insights.", icon="📊")

dataset = require_dataset(state)

if dataset is not None:
    outcome = state.current_cleaning_outcome
    outcome_matches = outcome is not None and outcome["dataset"]["dataset_id"] == dataset["dataset_id"]

    if not outcome_matches:
        st.warning("This dataset hasn't been cleaned yet. Run the Cleaning pipeline first, then return here.")
    else:
        assert outcome is not None  # guaranteed by outcome_matches
        if st.button("Run Analysis", type="primary"):
            client = APIClient(state.backend_url)
            new_analysis: dict[str, Any] | None
            with st.spinner("Analyzing dataset..."):
                try:
                    new_analysis = client.analyze(outcome)
                except APIClientError as exc:
                    render_api_error(exc)
                    new_analysis = None

            if new_analysis is not None:
                state.current_analysis = new_analysis
                state.current_visualization = None
                state.add_activity(f"Analyzed dataset '{dataset['dataset_name']}'.")

        analysis = state.current_analysis
        if analysis is not None and analysis.get("dataset_id") == dataset["dataset_id"]:
            for warning in analysis.get("warnings", []):
                st.warning(warning)

            tabs = st.tabs(["Summary", "KPIs", "Statistics", "Trends", "Correlations", "Anomalies", "Insights"])
            with tabs[0]:
                _render_summary(analysis["dataset_summary"])
            with tabs[1]:
                render_kpi_cards(analysis["kpis"])
            with tabs[2]:
                _render_statistics(analysis["descriptive_statistics"])
            with tabs[3]:
                _render_trends(analysis["trends"])
            with tabs[4]:
                _render_correlations(analysis["correlations"])
            with tabs[5]:
                _render_anomalies(analysis["anomalies"])
            with tabs[6]:
                render_insight_cards(analysis["insights"])
