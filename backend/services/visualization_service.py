"""Visualization entry point.

The only object anything (a future report, dashboard, chatbot response, or
executive summary) should use to visualize an ``AnalysisResult`` — never a
chart generator, the recommendation engine, or the layout engine directly.
Accepts an ``AnalysisResult`` and, optionally, the cleaned ``BusinessDataset``
it describes; resolves the DataFrame via the existing ``IngestionService``
when a dataset is given; runs the recommendation engine; organizes the
result into a layout; and returns one structured ``VisualizationResult``.
No PDF/PowerPoint generation, dashboards, or chatbot logic lives here.
"""

import time

from backend.analysis.models.result import AnalysisResult
from backend.ingestion.models.dataset import BusinessDataset
from backend.services.ingestion_service import IngestionService
from backend.utils.ids import generate_id
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.models.context import ChartContext
from backend.visualization.models.layout import LayoutType
from backend.visualization.models.result import VisualizationResult
from backend.visualization.recommendations.engine import ChartRecommendationEngine


class VisualizationService:
    """Generates recommended charts and a layout for an AnalysisResult. Never renders anything itself."""

    def __init__(
        self,
        ingestion_service: IngestionService,
        recommendation_engine: ChartRecommendationEngine,
        layout_engine: LayoutEngine,
    ) -> None:
        self._ingestion_service = ingestion_service
        self._recommendation_engine = recommendation_engine
        self._layout_engine = layout_engine

    def generate(
        self,
        analysis_result: AnalysisResult,
        dataset: BusinessDataset | None = None,
        layout_type: LayoutType = LayoutType.DETAILED_ANALYSIS,
    ) -> VisualizationResult:
        """Generate recommended charts and a layout for ``analysis_result``.

        ``dataset`` is optional: DataFrame-dependent charts (bar, scatter,
        histogram, pie, distribution, treemap) simply won't fire without
        it. If ``dataset`` is given but its DataFrame can't be resolved,
        that's recorded as a warning — never a hard failure — and
        generation proceeds as if no dataset had been given at all.
        """
        start = time.perf_counter()
        warnings: list[str] = []

        dataframe = None
        if dataset is not None:
            dataframe = self._ingestion_service.get_dataframe(dataset)
            if dataframe is None:
                warnings.append(
                    f"No DataFrame found for dataset '{dataset.dataset_id}'; "
                    "falling back to AnalysisResult-only chart generation."
                )

        context = ChartContext(analysis_result=analysis_result, dataframe=dataframe)
        recommendation_result = self._recommendation_engine.recommend(context)
        layout = self._layout_engine.build(layout_type, recommendation_result.charts)

        recommendations = [
            f"Recommended {chart.chart_type.value}: {chart.description or chart.title}"
            for chart in recommendation_result.charts
        ]
        recommendations.extend(
            f"Skipped {skipped.chart_type.value}: {skipped.reason}" for skipped in recommendation_result.skipped
        )

        execution_time = time.perf_counter() - start
        return VisualizationResult(
            visualization_id=generate_id(),
            analysis_id=analysis_result.analysis_id,
            charts=recommendation_result.charts,
            layout=layout,
            recommendations=recommendations,
            warnings=warnings,
            metadata={"generated_by": "visualization_service"},
            execution_time=execution_time,
        )
