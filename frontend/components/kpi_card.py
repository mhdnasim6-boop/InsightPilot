"""KPI card component: renders AnalysisResult.kpis as a grid of metrics."""

from typing import Any

import streamlit as st

from frontend.utils.formatting import format_number, format_percent

_PERCENT_KPI_TYPES = {"null_percentage"}


def render_kpi_cards(kpis: list[dict[str, Any]], columns_per_row: int = 4) -> None:
    """Render a grid of KPI cards using ``st.metric``.

    ``kpis`` is the ``AnalysisResult.kpis`` list as returned by the API
    client — plain dicts shaped like ``{name, kpi_type, column, value}``.
    Whether a value is displayed with a "%" suffix is a display decision
    keyed off ``kpi_type``, not a recomputation: ``KPIEngine`` already
    scales percentage-style KPIs onto a 0-100 range before this ever runs.
    """
    if not kpis:
        st.info("No KPIs available for this dataset.")
        return

    rows = [kpis[i : i + columns_per_row] for i in range(0, len(kpis), columns_per_row)]
    for row in rows:
        cols = st.columns(columns_per_row)
        for col, kpi in zip(cols, row, strict=False):
            with col:
                value = kpi.get("value")
                is_percent = kpi.get("kpi_type") in _PERCENT_KPI_TYPES
                display_value = format_percent(value) if is_percent else format_number(value)
                st.metric(label=kpi.get("name", "KPI"), value=display_value)
