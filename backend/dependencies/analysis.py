"""Analysis providers: every analyzer engine, plus the analysis service."""

from functools import lru_cache

from fastapi import Depends

from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.anomalies.engine import AnomalyEngine
from backend.analysis.correlations.engine import CorrelationEngine
from backend.analysis.insights.engine import InsightEngine
from backend.analysis.kpis.engine import KPIEngine
from backend.analysis.statistics.engine import DescriptiveStatisticsEngine
from backend.analysis.trends.engine import TrendEngine
from backend.dependencies.ingestion import get_ingestion_service
from backend.services.analysis_service import AnalysisService
from backend.services.ingestion_service import IngestionService


@lru_cache
def get_descriptive_statistics_engine() -> DescriptiveStatisticsEngine:
    """Return the process-wide DescriptiveStatisticsEngine singleton (stateless, safe to share)."""
    return DescriptiveStatisticsEngine()


@lru_cache
def get_kpi_engine() -> KPIEngine:
    """Return the process-wide KPIEngine singleton (stateless, safe to share)."""
    return KPIEngine()


@lru_cache
def get_trend_engine() -> TrendEngine:
    """Return the process-wide TrendEngine singleton (stateless, safe to share)."""
    return TrendEngine()


@lru_cache
def get_correlation_engine() -> CorrelationEngine:
    """Return the process-wide CorrelationEngine singleton (stateless, safe to share)."""
    return CorrelationEngine()


@lru_cache
def get_anomaly_engine() -> AnomalyEngine:
    """Return the process-wide AnomalyEngine singleton (stateless, safe to share)."""
    return AnomalyEngine()


@lru_cache
def get_aggregation_engine() -> AggregationEngine:
    """Return the process-wide AggregationEngine singleton (stateless, safe to share).

    Also usable directly by future dashboard/report modules — not
    exclusively an InsightEngine implementation detail.
    """
    return AggregationEngine()


@lru_cache
def get_insight_engine(aggregation_engine: AggregationEngine = Depends(get_aggregation_engine)) -> InsightEngine:
    """Return the process-wide InsightEngine singleton (stateless, safe to share)."""
    return InsightEngine(aggregation_engine)


def get_analysis_service(
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    descriptive_statistics_engine: DescriptiveStatisticsEngine = Depends(get_descriptive_statistics_engine),
    kpi_engine: KPIEngine = Depends(get_kpi_engine),
    trend_engine: TrendEngine = Depends(get_trend_engine),
    correlation_engine: CorrelationEngine = Depends(get_correlation_engine),
    anomaly_engine: AnomalyEngine = Depends(get_anomaly_engine),
    insight_engine: InsightEngine = Depends(get_insight_engine),
) -> AnalysisService:
    """Provide the AnalysisService — the only object that should be used for business analysis."""
    return AnalysisService(
        ingestion_service,
        descriptive_statistics_engine,
        kpi_engine,
        trend_engine,
        correlation_engine,
        anomaly_engine,
        insight_engine,
    )
