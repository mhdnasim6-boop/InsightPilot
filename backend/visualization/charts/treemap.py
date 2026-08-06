"""Treemap placeholder generator.

Fires when a high-cardinality categorical column is detected — mirrors
``backend.analysis.models.anomaly.IsolationForestPlaceholder``: an honest,
structured "not implemented" rather than a fake chart.
"""

from backend.utils.ids import generate_id
from backend.visualization.charts.base import ChartGenerator
from backend.visualization.models.chart import ChartSpecification, ChartType
from backend.visualization.models.context import ChartContext


class TreemapPlaceholderGenerator(ChartGenerator):
    """Detects high-cardinality categorical columns; produces a placeholder spec, not a real treemap."""

    chart_type = ChartType.TREEMAP

    def __init__(self, cardinality_threshold: int = 20) -> None:
        self._cardinality_threshold = cardinality_threshold

    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        if context.dataframe is None:
            return False, "No dataset provided; cannot assess categorical cardinality."
        if not self._high_cardinality_columns(context):
            return False, "No high-cardinality categorical column detected."
        return True, None

    def generate(self, context: ChartContext) -> ChartSpecification:
        dataframe = context.dataframe
        assert dataframe is not None  # applicable() already confirmed this
        column = max(self._high_cardinality_columns(context), key=lambda name: dataframe[name].nunique())

        return ChartSpecification(
            chart_id=f"treemap_{generate_id()}",
            title=f"{column} Breakdown (Treemap)",
            chart_type=ChartType.TREEMAP,
            series=[],
            description=(
                f"High-cardinality column '{column}' detected ({dataframe[column].nunique()} unique values); "
                "treemap rendering is a placeholder in this phase."
            ),
            priority=1,
            metadata={
                "implemented": False,
                "column": column,
                "note": "Treemap chart generation is a placeholder for a future release; not rendered in this phase.",
            },
        )

    def _high_cardinality_columns(self, context: ChartContext) -> list[str]:
        dataframe = context.dataframe
        if dataframe is None:
            return []
        categorical = [
            column for column in context.analysis_result.dataset_summary.categorical_columns if column in dataframe.columns
        ]
        return [column for column in categorical if dataframe[column].nunique() > self._cardinality_threshold]
