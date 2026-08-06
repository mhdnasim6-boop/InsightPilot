"""Generic matrix-to-heatmap builder, plus the two generators that use it.

``HeatmapGenerator`` and ``CorrelationMatrixGenerator`` are functionally
similar today because correlation data is the only 2D matrix
``AnalysisResult`` currently provides — ``HeatmapGenerator`` is kept as
the general-purpose building block for any future matrix data (e.g. a
cross-tab pivot), while ``CorrelationMatrixGenerator`` is specifically,
permanently labeled "Correlation Matrix". Only ``CorrelationMatrixGenerator``
is registered by default (see ``registry.py``) to avoid two near-duplicate
heatmap charts appearing in the same result.
"""

from typing import Any

from backend.utils.ids import generate_id
from backend.visualization.charts.base import ChartGenerator
from backend.visualization.models.chart import (
    AxisSpec,
    ChartSeries,
    ChartSpecification,
    ChartType,
)
from backend.visualization.models.context import ChartContext


def build_heatmap_chart_spec(
    chart_id: str,
    title: str,
    matrix: dict[str, dict[str, Any]],
    columns: list[str],
    chart_type: ChartType = ChartType.HEATMAP,
    description: str | None = None,
    priority: int = 0,
) -> ChartSpecification:
    """Build a heatmap-shaped ``ChartSpecification`` from any square, labeled matrix."""
    z = [[matrix.get(row, {}).get(column) for column in columns] for row in columns]
    series = [ChartSeries(name=title, x=columns, y=columns, z=z)]
    return ChartSpecification(
        chart_id=chart_id,
        title=title,
        chart_type=chart_type,
        x_axis=AxisSpec(label="Column", data_type="categorical"),
        y_axis=AxisSpec(label="Column", data_type="categorical"),
        series=series,
        description=description,
        priority=priority,
    )


class HeatmapGenerator(ChartGenerator):
    """General-purpose heatmap generator. Defaults to correlation data (the only matrix available today)."""

    chart_type = ChartType.HEATMAP

    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        correlations = context.analysis_result.correlations
        if not correlations.applicable:
            return False, correlations.reason or "No matrix data available for a heatmap."
        return True, None

    def generate(self, context: ChartContext) -> ChartSpecification:
        correlations = context.analysis_result.correlations
        return build_heatmap_chart_spec(
            chart_id=f"heatmap_{generate_id()}",
            title="Correlation Heatmap",
            matrix=correlations.pearson_matrix,
            columns=correlations.columns,
            chart_type=ChartType.HEATMAP,
            description="Pearson correlation heatmap across numeric columns.",
            priority=7,
        )


class CorrelationMatrixGenerator(ChartGenerator):
    """Builds the Pearson correlation matrix chart from AnalysisResult.correlations."""

    chart_type = ChartType.CORRELATION_MATRIX

    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        correlations = context.analysis_result.correlations
        if not correlations.applicable:
            return False, correlations.reason or "Correlation analysis was not applicable."
        return True, None

    def generate(self, context: ChartContext) -> ChartSpecification:
        correlations = context.analysis_result.correlations
        return build_heatmap_chart_spec(
            chart_id=f"correlation_matrix_{generate_id()}",
            title="Correlation Matrix",
            matrix=correlations.pearson_matrix,
            columns=correlations.columns,
            chart_type=ChartType.CORRELATION_MATRIX,
            description=f"Pearson correlation matrix for {len(correlations.columns)} numeric column(s).",
            priority=7,
        )
