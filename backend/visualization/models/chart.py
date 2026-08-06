"""The chart specification: a Plotly-independent description of one chart.

Any rendering library could draw a chart from a ``ChartSpecification`` —
Plotly is an internal detail of ``backend.visualization.exporters``, never
imported by this module.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChartType(str, Enum):
    """Every chart type this layer knows how to describe.

    ``TREEMAP`` is a recognized-but-placeholder type (mirrors
    ``IsolationForestPlaceholder`` from the analysis layer) — no
    hierarchical rendering is implemented in this phase.
    """

    BAR = "bar"
    LINE = "line"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    BOX = "box"
    PIE = "pie"
    HEATMAP = "heatmap"
    CORRELATION_MATRIX = "correlation_matrix"
    DISTRIBUTION = "distribution"
    KPI_CARD = "kpi_card"
    TREEMAP = "treemap"


class AxisSpec(BaseModel):
    """Describes one chart axis."""

    label: str
    column: str | None = None
    data_type: str | None = None


class ChartSeries(BaseModel):
    """One data series within a chart.

    ``z`` carries 2D matrix data (heatmaps, correlation matrices); ``x``/
    ``y`` cover every 1D chart type, including KPI cards (``x`` holds the
    KPI name, ``y`` holds its value) — one uniform shape for all 11 chart
    types, no special-casing in the model itself.
    """

    name: str
    x: list[Any] = Field(default_factory=list)
    y: list[Any] = Field(default_factory=list)
    z: list[list[Any]] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChartSpecification(BaseModel):
    """A complete, rendering-independent description of one chart."""

    chart_id: str
    title: str
    chart_type: ChartType
    x_axis: AxisSpec | None = None
    y_axis: AxisSpec | None = None
    series: list[ChartSeries] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    description: str | None = None
    priority: int = 0
    interactive: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
