"""Tests for exporters: JSON, PNG/SVG placeholders, and the Plotly renderer."""

import json

import plotly.graph_objects as go
import pytest

from backend.visualization.exceptions.errors import UnknownChartTypeError
from backend.visualization.exporters.image_placeholders import PNGExporter, SVGExporter
from backend.visualization.exporters.json_exporter import JSONExporter
from backend.visualization.exporters.plotly_exporter import PlotlyExporter
from backend.visualization.models.chart import (
    AxisSpec,
    ChartSeries,
    ChartSpecification,
    ChartType,
)
from backend.visualization.themes.registry import ThemeRegistry


def _bar_spec() -> ChartSpecification:
    return ChartSpecification(
        chart_id="bar_1",
        title="Revenue by Region",
        chart_type=ChartType.BAR,
        x_axis=AxisSpec(label="Region"),
        y_axis=AxisSpec(label="Revenue"),
        series=[ChartSeries(name="revenue", x=["East", "West"], y=[100, 50])],
    )


def test_json_exporter_round_trips_the_spec() -> None:
    spec = _bar_spec()
    raw = JSONExporter().export(spec)
    data = json.loads(raw)
    assert data["chart_id"] == "bar_1"
    assert data["series"][0]["y"] == [100, 50]


def test_png_exporter_is_an_explicit_placeholder() -> None:
    result = PNGExporter().export(_bar_spec())
    assert result.implemented is False
    assert result.format == "png"


def test_svg_exporter_is_an_explicit_placeholder() -> None:
    result = SVGExporter().export(_bar_spec())
    assert result.implemented is False
    assert result.format == "svg"


@pytest.mark.parametrize(
    ("chart_type", "series"),
    [
        (ChartType.BAR, [ChartSeries(name="s", x=["a", "b"], y=[1, 2])]),
        (ChartType.LINE, [ChartSeries(name="s", y=[1, 2, 3])]),
        (ChartType.SCATTER, [ChartSeries(name="s", x=[1, 2], y=[3, 4])]),
        (ChartType.HISTOGRAM, [ChartSeries(name="s", x=["0-1", "1-2"], y=[3, 5])]),
        (ChartType.BOX, [ChartSeries(name="s", metadata={"q1": 1, "median": 2, "q3": 3, "min": 0, "max": 4})]),
        (ChartType.PIE, [ChartSeries(name="s", x=["a", "b"], y=[1, 2])]),
        (ChartType.HEATMAP, [ChartSeries(name="s", x=["a"], y=["a"], z=[[1.0]])]),
        (ChartType.CORRELATION_MATRIX, [ChartSeries(name="s", x=["a"], y=["a"], z=[[1.0]])]),
        (ChartType.DISTRIBUTION, [ChartSeries(name="s", x=[1, 2, 3])]),
        (ChartType.KPI_CARD, [ChartSeries(name="Revenue", x=["Revenue"], y=[100])]),
        (ChartType.TREEMAP, []),
    ],
)
def test_plotly_exporter_renders_every_chart_type(chart_type: ChartType, series: list[ChartSeries]) -> None:
    spec = ChartSpecification(chart_id="c1", title="Chart", chart_type=chart_type, series=series)
    figure = PlotlyExporter().export(spec)
    assert isinstance(figure, go.Figure)


def test_plotly_exporter_applies_a_theme() -> None:
    theme = ThemeRegistry().get("dark")
    figure = PlotlyExporter().export(_bar_spec(), theme=theme)
    assert figure.layout.paper_bgcolor == theme.background_color


def test_plotly_exporter_kpi_card_uses_one_indicator_per_series() -> None:
    spec = ChartSpecification(
        chart_id="kpi_1",
        title="KPIs",
        chart_type=ChartType.KPI_CARD,
        series=[
            ChartSeries(name="Revenue", x=["Revenue"], y=[100]),
            ChartSeries(name="Orders", x=["Orders"], y=[7]),
        ],
    )
    figure = PlotlyExporter().export(spec)
    assert len(figure.data) == 2
    assert all(trace.type == "indicator" for trace in figure.data)


def test_plotly_exporter_raises_for_an_unregistered_chart_type() -> None:
    exporter = PlotlyExporter()
    exporter._trace_builders.clear()  # simulate no renderer registered, to exercise the guard clause
    spec = _bar_spec()
    with pytest.raises(UnknownChartTypeError):
        exporter.export(spec)
