"""Integration tests for VisualizationService: visualize a real analyzed dataset end to end."""

from pathlib import Path

from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.anomalies.engine import AnomalyEngine
from backend.analysis.correlations.engine import CorrelationEngine
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
from backend.services.visualization_service import VisualizationService
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.models.layout import LayoutType
from backend.visualization.recommendations.engine import ChartRecommendationEngine


def _make_services() -> tuple[IngestionService, CleaningService, AnalysisService, VisualizationService]:
    dataframe_store = DataFrameStore()
    extractor = MetadataExtractor()
    ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), extractor, dataframe_store)
    cleaning_service = CleaningService(
        ingestion_service, DatasetProfilingService(extractor), extractor, dataframe_store
    )
    aggregation_engine = AggregationEngine()
    analysis_service = AnalysisService(
        ingestion_service,
        DescriptiveStatisticsEngine(),
        KPIEngine(),
        TrendEngine(),
        CorrelationEngine(),
        AnomalyEngine(),
        InsightEngine(aggregation_engine),
    )
    generators = default_generators(aggregation_engine)
    visualization_service = VisualizationService(
        ingestion_service, ChartRecommendationEngine(generators), LayoutEngine()
    )
    return ingestion_service, cleaning_service, analysis_service, visualization_service


_CSV_CONTENT = (
    "date,region,revenue,cost\n"
    "2024-01-01,East,1000,600\n"
    "2024-02-01,East,1100,650\n"
    "2024-03-01,East,1180,680\n"
    "2024-01-01,West,200,120\n"
    "2024-02-01,West,210,130\n"
    "2024-03-01,West,9000,5000\n"
)


def test_generate_with_dataset_produces_dataframe_dependent_and_analysis_only_charts(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text(_CSV_CONTENT)
    ingestion_service, cleaning_service, analysis_service, visualization_service = _make_services()

    dataset = ingestion_service.ingest(str(csv_file))
    outcome = cleaning_service.clean(dataset)
    analysis_result = analysis_service.analyze(outcome)

    result = visualization_service.generate(analysis_result, dataset=outcome.dataset)

    assert result.analysis_id == analysis_result.analysis_id
    chart_types = {chart.chart_type.value for chart in result.charts}
    assert "kpi_card" in chart_types
    assert "line" in chart_types  # trend-based, AnalysisResult-only
    assert "correlation_matrix" in chart_types  # AnalysisResult-only
    assert "bar" in chart_types  # DataFrame-dependent
    assert "scatter" in chart_types  # DataFrame-dependent
    assert len(result.recommendations) > 0
    assert result.warnings == []
    assert result.execution_time >= 0.0
    assert result.visualization_id


def test_generate_without_dataset_only_produces_analysis_result_only_charts(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text(_CSV_CONTENT)
    ingestion_service, cleaning_service, analysis_service, visualization_service = _make_services()

    dataset = ingestion_service.ingest(str(csv_file))
    outcome = cleaning_service.clean(dataset)
    analysis_result = analysis_service.analyze(outcome)

    result = visualization_service.generate(analysis_result)  # no dataset given

    chart_types = {chart.chart_type.value for chart in result.charts}
    assert "kpi_card" in chart_types
    assert "line" in chart_types
    assert "correlation_matrix" in chart_types
    assert "bar" not in chart_types  # needs a DataFrame
    assert "scatter" not in chart_types
    assert any("bar" in skip for skip in result.recommendations if skip.startswith("Skipped"))


def test_generate_builds_the_requested_layout_type(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text(_CSV_CONTENT)
    ingestion_service, cleaning_service, analysis_service, visualization_service = _make_services()

    dataset = ingestion_service.ingest(str(csv_file))
    outcome = cleaning_service.clean(dataset)
    analysis_result = analysis_service.analyze(outcome)

    result = visualization_service.generate(
        analysis_result, dataset=outcome.dataset, layout_type=LayoutType.EXECUTIVE_SUMMARY
    )

    assert result.layout.layout_type == LayoutType.EXECUTIVE_SUMMARY
    assert any(section.title == "Key Metrics" for section in result.layout.sections)


def test_generate_warns_gracefully_when_the_dataset_has_no_stored_dataframe(tmp_path: Path) -> None:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text(_CSV_CONTENT)
    ingestion_service, cleaning_service, analysis_service, _ = _make_services()

    dataset = ingestion_service.ingest(str(csv_file))
    outcome = cleaning_service.clean(dataset)
    analysis_result = analysis_service.analyze(outcome)

    # A fresh, empty DataFrameStore means the dataset's DataFrame can't be resolved.
    isolated_store = DataFrameStore()
    extractor = MetadataExtractor()
    isolated_ingestion_service = IngestionService(LoaderRegistry(), DatasetValidator(), extractor, isolated_store)
    aggregation_engine = AggregationEngine()
    isolated_visualization_service = VisualizationService(
        isolated_ingestion_service,
        ChartRecommendationEngine(default_generators(aggregation_engine)),
        LayoutEngine(),
    )

    result = isolated_visualization_service.generate(analysis_result, dataset=outcome.dataset)

    assert len(result.warnings) == 1
    assert "No DataFrame found" in result.warnings[0]
    assert all(chart.chart_type.value != "bar" for chart in result.charts)
