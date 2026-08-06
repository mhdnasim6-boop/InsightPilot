"""Assembles the default set of chart generators the recommendation engine runs.

``HeatmapGenerator`` is deliberately excluded here (see
``heatmap.py``'s module docstring) — ``CorrelationMatrixGenerator``
already covers the "correlation matrix exists" recommendation rule, and
registering both would produce two near-duplicate charts.
"""

from backend.analysis.aggregations.engine import AggregationEngine
from backend.visualization.charts.bar import BarChartGenerator
from backend.visualization.charts.base import ChartGenerator
from backend.visualization.charts.box import BoxPlotGenerator
from backend.visualization.charts.distribution import DistributionPlotGenerator
from backend.visualization.charts.heatmap import CorrelationMatrixGenerator
from backend.visualization.charts.histogram import HistogramGenerator
from backend.visualization.charts.kpi_cards import KPICardGenerator
from backend.visualization.charts.line import LineChartGenerator
from backend.visualization.charts.pie import PieChartGenerator
from backend.visualization.charts.scatter import ScatterPlotGenerator
from backend.visualization.charts.treemap import TreemapPlaceholderGenerator


def default_generators(aggregation_engine: AggregationEngine) -> tuple[ChartGenerator, ...]:
    """Return one instance of every default-registered chart generator.

    A tuple, not a list: this return value is passed straight into an
    ``lru_cache``-decorated DI provider (``get_chart_recommendation_engine``),
    which needs every argument to be hashable.
    """
    return (
        KPICardGenerator(),
        LineChartGenerator(),
        BarChartGenerator(aggregation_engine),
        PieChartGenerator(aggregation_engine),
        ScatterPlotGenerator(),
        CorrelationMatrixGenerator(),
        BoxPlotGenerator(),
        DistributionPlotGenerator(),
        HistogramGenerator(),
        TreemapPlaceholderGenerator(),
    )
