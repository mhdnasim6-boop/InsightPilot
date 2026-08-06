"""Business analysis entry point.

The only object anything (a future visualization/report/chatbot/AI agent)
should use to analyze a cleaned dataset — never a single analyzer engine
directly. Accepts a ``CleaningOutcome``, resolves the cleaned DataFrame via
the existing ``IngestionService``, runs every analyzer, and returns one
structured ``AnalysisResult``. No visualization, no report generation, no
AI-generated insights.
"""

import time

from backend.analysis.anomalies.engine import AnomalyEngine
from backend.analysis.correlations.engine import CorrelationEngine
from backend.analysis.exceptions.errors import DataFrameNotFoundError
from backend.analysis.insights.engine import InsightEngine
from backend.analysis.kpis.engine import KPIEngine
from backend.analysis.models.result import AnalysisResult
from backend.analysis.profiling.dataset_summary import build_dataset_summary
from backend.analysis.statistics.engine import DescriptiveStatisticsEngine
from backend.analysis.trends.engine import TrendEngine
from backend.cleaning.models.outcome import CleaningOutcome
from backend.services.ingestion_service import IngestionService
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class AnalysisService:
    """Runs every deterministic analyzer against a cleaned dataset and returns one AnalysisResult."""

    def __init__(
        self,
        ingestion_service: IngestionService,
        descriptive_statistics_engine: DescriptiveStatisticsEngine,
        kpi_engine: KPIEngine,
        trend_engine: TrendEngine,
        correlation_engine: CorrelationEngine,
        anomaly_engine: AnomalyEngine,
        insight_engine: InsightEngine,
    ) -> None:
        self._ingestion_service = ingestion_service
        self._descriptive_statistics_engine = descriptive_statistics_engine
        self._kpi_engine = kpi_engine
        self._trend_engine = trend_engine
        self._correlation_engine = correlation_engine
        self._anomaly_engine = anomaly_engine
        self._insight_engine = insight_engine

    def analyze(self, cleaning_outcome: CleaningOutcome) -> AnalysisResult:
        """Run every analyzer against ``cleaning_outcome``'s cleaned dataset.

        Raises ``DataFrameNotFoundError`` if the cleaned dataset has no
        resolvable DataFrame in the DataFrameStore.
        """
        start = time.perf_counter()
        dataset = cleaning_outcome.dataset
        dataframe = self._ingestion_service.get_dataframe(dataset)
        if dataframe is None:
            raise DataFrameNotFoundError(f"No DataFrame found for dataset '{dataset.dataset_id}'; cannot analyze.")

        dataset_summary = build_dataset_summary(cleaning_outcome.profile)
        descriptive_statistics = self._descriptive_statistics_engine.compute(dataframe)
        kpis = self._kpi_engine.compute(dataframe)
        trends = self._trend_engine.analyze(dataframe)
        correlations = self._correlation_engine.analyze(dataframe)
        anomalies = self._anomaly_engine.analyze(dataframe)
        insights = self._insight_engine.generate(
            dataframe, cleaning_outcome.profile, dataset_summary, trends, anomalies, correlations
        )

        execution_time = time.perf_counter() - start

        return AnalysisResult(
            analysis_id=generate_id(),
            dataset_id=dataset.dataset_id,
            analysis_timestamp=utc_now(),
            dataset_summary=dataset_summary,
            descriptive_statistics=descriptive_statistics,
            kpis=kpis,
            trends=trends,
            anomalies=anomalies,
            correlations=correlations,
            insights=insights,
            metadata={"generated_by": "analysis_service"},
            execution_time=execution_time,
        )
