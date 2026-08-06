"""Renders a ChartSpecification as a real Plotly Figure.

The ONLY file in this entire project that imports ``plotly`` — a future
rendering library would only need a new exporter class here; nothing that
produces or consumes a ``ChartSpecification`` would ever change.
"""

from collections.abc import Callable
from typing import Any

import plotly.graph_objects as go

from backend.visualization.exceptions.errors import UnknownChartTypeError
from backend.visualization.models.chart import (
    ChartSeries,
    ChartSpecification,
    ChartType,
)
from backend.visualization.models.theme import Theme

# plotly ships no type stubs, so its real trace base class
# (plotly.basedatatypes.BaseTraceType, not exported from graph_objects)
# isn't a usable annotation here — every trace builder returns `Any`.
TraceBuilder = Callable[[ChartSeries], Any]


class PlotlyExporter:
    """Converts a ChartSpecification into a ``plotly.graph_objects.Figure``, optionally themed.

    KPI cards are handled separately from the rest: a ``go.Indicator``
    needs an explicit grid ``domain`` per card to avoid overlapping, so
    building that figure needs series *indices*, unlike every other chart
    type where each series maps independently to one trace.
    """

    def __init__(self) -> None:
        self._trace_builders: dict[ChartType, TraceBuilder] = {
            ChartType.BAR: self._bar_trace,
            ChartType.LINE: self._line_trace,
            ChartType.SCATTER: self._scatter_trace,
            ChartType.HISTOGRAM: self._histogram_trace,
            ChartType.BOX: self._box_trace,
            ChartType.PIE: self._pie_trace,
            ChartType.HEATMAP: self._heatmap_trace,
            ChartType.CORRELATION_MATRIX: self._heatmap_trace,
            ChartType.DISTRIBUTION: self._distribution_trace,
            ChartType.TREEMAP: self._treemap_placeholder_trace,
        }

    def export(self, spec: ChartSpecification, theme: Theme | None = None) -> go.Figure:
        """Render ``spec`` as a Plotly Figure, applying ``theme`` if given."""
        if spec.chart_type == ChartType.KPI_CARD:
            figure = self._build_kpi_card_figure(spec)
        else:
            figure = self._build_standard_figure(spec)

        if theme is not None:
            self._apply_theme(figure, theme)
        return figure

    def _build_standard_figure(self, spec: ChartSpecification) -> go.Figure:
        builder = self._trace_builders.get(spec.chart_type)
        if builder is None:
            raise UnknownChartTypeError(f"No Plotly renderer registered for chart type '{spec.chart_type.value}'.")

        figure = go.Figure()
        for series in spec.series:
            figure.add_trace(builder(series))

        figure.update_layout(
            title=spec.title,
            xaxis_title=spec.x_axis.label if spec.x_axis else None,
            yaxis_title=spec.y_axis.label if spec.y_axis else None,
        )
        return figure

    def _build_kpi_card_figure(self, spec: ChartSpecification) -> go.Figure:
        figure = go.Figure()
        total_cards = max(len(spec.series), 1)
        for index, series in enumerate(spec.series):
            value = series.y[0] if series.y else None
            figure.add_trace(
                go.Indicator(mode="number", value=value, title={"text": series.name}, domain={"row": 0, "column": index})
            )
        figure.update_layout(
            title=spec.title, grid={"rows": 1, "columns": total_cards, "pattern": "independent"}
        )
        return figure

    def _apply_theme(self, figure: go.Figure, theme: Theme) -> None:
        figure.update_layout(
            paper_bgcolor=theme.background_color,
            plot_bgcolor=theme.background_color,
            font={"color": theme.font_color},
            colorway=theme.color_palette or None,
        )
        figure.update_xaxes(gridcolor=theme.grid_color)
        figure.update_yaxes(gridcolor=theme.grid_color)

    def _bar_trace(self, series: ChartSeries) -> go.Bar:
        return go.Bar(x=series.x, y=series.y, name=series.name)

    def _line_trace(self, series: ChartSeries) -> go.Scatter:
        # TrendSeriesResult doesn't carry actual time-axis labels today, so
        # a positional index is used when the series has no explicit x —
        # see the Future Extensibility notes in the README.
        x_values = series.x or list(range(len(series.y)))
        return go.Scatter(x=x_values, y=series.y, mode="lines", name=series.name)

    def _scatter_trace(self, series: ChartSeries) -> go.Scatter:
        return go.Scatter(x=series.x, y=series.y, mode="markers", name=series.name)

    def _histogram_trace(self, series: ChartSeries) -> go.Bar:
        # HistogramGenerator pre-bins the data (labels + counts); a Bar
        # trace renders that directly, rather than go.Histogram (which
        # expects raw, unbinned values).
        return go.Bar(x=series.x, y=series.y, name=series.name)

    def _box_trace(self, series: ChartSeries) -> go.Box:
        metadata = series.metadata
        return go.Box(
            name=series.name,
            q1=[metadata.get("q1")],
            median=[metadata.get("median")],
            q3=[metadata.get("q3")],
            lowerfence=[metadata.get("min")],
            upperfence=[metadata.get("max")],
        )

    def _pie_trace(self, series: ChartSeries) -> go.Pie:
        return go.Pie(labels=series.x, values=series.y, name=series.name)

    def _heatmap_trace(self, series: ChartSeries) -> go.Heatmap:
        return go.Heatmap(x=series.x, y=series.y, z=series.z, colorscale="RdBu", zmid=0)

    def _distribution_trace(self, series: ChartSeries) -> go.Histogram:
        return go.Histogram(x=series.x, name=series.name)

    def _treemap_placeholder_trace(self, series: ChartSeries) -> go.Bar:
        # No real treemap rendering in this phase; TreemapPlaceholderGenerator
        # always produces an empty `series`, so this never actually runs —
        # registered anyway so export() succeeds (an empty, titled figure)
        # rather than raising for a legitimate placeholder chart type.
        return go.Bar(x=[], y=[], name=series.name)
