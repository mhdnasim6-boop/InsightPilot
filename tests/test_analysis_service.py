"""Integration tests for AnalysisService: analyze a real cleaned dataset end to end."""

from pathlib import Path

import pytest

from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.anomalies.engine import AnomalyEngine
from backend.analysis.correlations.engine import CorrelationEngine
from backend.analysis.exceptions.errors import DataFrameNotFoundError
from backend.analysis.insights.engine import InsightEngine
from backend.analysis.kpis.engine import KPIEngine
from backend.analysis.statistics.engine import DescriptiveStatisticsEngine
from backend.analysis.trends.engine import TrendEngine
from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.services.analysis_service import AnalysisService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService


def _make_services() -> tuple[IngestionService, CleaningService, AnalysisService]:
    dataframe_store = DataFrameStore()
    extractor = MetadataExtractor()
    ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), extractor, dataframe_store)
    cleaning_service = CleaningService(
        ingestion_service, DatasetProfilingService(extractor), extractor, dataframe_store
    )
    analysis_service = AnalysisService(
        ingestion_service,
        DescriptiveStatisticsEngine(),
        KPIEngine(),
        TrendEngine(),
        CorrelationEngine(),
        AnomalyEngine(),
        InsightEngine(AggregationEngine()),
    )
    return ingestion_service, cleaning_service, analysis_service


def test_analyze_produces_a_fully_populated_result(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text(
        "date,region,revenue,cost\n"
        "2024-01-01,East,1000,600\n"
        "2024-02-01,East,1100,650\n"
        "2024-03-01,East,1180,680\n"
        "2024-01-01,West,200,120\n"
        "2024-02-01,West,210,130\n"
        "2024-03-01,West,9000,5000\n"
    )
    ingestion_service, cleaning_service, analysis_service = _make_services()
    dataset = ingestion_service.ingest(str(csv_file))
    outcome = cleaning_service.clean(dataset)

    result = analysis_service.analyze(outcome)

    assert result.dataset_id == outcome.dataset.dataset_id
    assert result.dataset_summary.row_count == 6
    assert set(result.descriptive_statistics.columns) == {"revenue", "cost"}
    assert len(result.kpis) > 0
    assert result.trends.applicable is True
    assert result.trends.time_column == "date"
    assert result.correlations.applicable is True
    assert result.anomalies.applicable is True
    assert len(result.insights) > 0
    assert result.execution_time >= 0.0
    assert result.analysis_id


def test_analyze_raises_dataframe_not_found_when_no_dataframe_is_stored(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text("region,amount\nEast,100\n")
    ingestion_service, cleaning_service, _ = _make_services()
    dataset = ingestion_service.ingest(str(csv_file))
    outcome = cleaning_service.clean(dataset)

    # Simulate a store that has lost the cleaned DataFrame (e.g. evicted).
    fresh_store = DataFrameStore()
    extractor = MetadataExtractor()
    isolated_ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), extractor, fresh_store)
    isolated_analysis_service = AnalysisService(
        isolated_ingestion_service,
        DescriptiveStatisticsEngine(),
        KPIEngine(),
        TrendEngine(),
        CorrelationEngine(),
        AnomalyEngine(),
        InsightEngine(AggregationEngine()),
    )

    with pytest.raises(DataFrameNotFoundError):
        isolated_analysis_service.analyze(outcome)


def test_analyze_reports_not_applicable_sections_gracefully(tmp_path: Path) -> None:
    csv_file = tmp_path / "single_numeric.csv"
    csv_file.write_text("region,amount\nEast,100\nWest,200\n")
    ingestion_service, cleaning_service, analysis_service = _make_services()
    dataset = ingestion_service.ingest(str(csv_file))
    outcome = cleaning_service.clean(dataset)

    result = analysis_service.analyze(outcome)

    assert result.trends.applicable is False
    assert result.correlations.applicable is False  # only one numeric column
