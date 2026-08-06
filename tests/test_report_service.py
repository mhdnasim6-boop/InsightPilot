"""Tests for ReportService: build/get/list/validate/export over a real
ingested / cleaned / analyzed / visualized pipeline.
"""

from pathlib import Path

import pytest

from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.anomalies.engine import AnomalyEngine
from backend.analysis.correlations.engine import CorrelationEngine
from backend.analysis.insights.engine import InsightEngine
from backend.analysis.kpis.engine import KPIEngine
from backend.analysis.models.result import AnalysisResult
from backend.analysis.statistics.engine import DescriptiveStatisticsEngine
from backend.analysis.trends.engine import TrendEngine
from backend.cleaning.models.outcome import CleaningOutcome
from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.models.dataset import BusinessDataset
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.exceptions.errors import (
    ReportNotFoundError,
    ReportValidationFailedError,
)
from backend.reporting.models.report_document import ReportExportFormat
from backend.reporting.report_store import ReportStore
from backend.reporting.templates.report_template import ReportTemplateType
from backend.reporting.validation.validator import ReportValidator
from backend.services.analysis_service import AnalysisService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from backend.services.report_service import ReportService
from backend.services.visualization_service import VisualizationService
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
from backend.visualization.models.placeholder import ExportPlaceholder
from backend.visualization.models.result import VisualizationResult
from backend.visualization.recommendations.engine import ChartRecommendationEngine

_CSV_CONTENT = (
    "date,region,revenue,cost\n"
    "2024-01-01,East,1000,600\n"
    "2024-02-01,East,1100,650\n"
    "2024-03-01,East,1180,680\n"
    "2024-01-01,West,200,120\n"
    "2024-02-01,West,210,130\n"
    "2024-03-01,West,9000,5000\n"
)


def _make_report_service() -> ReportService:
    return ReportService(ReportBuilder(), ReportValidator(), ReportStore())


def _make_pipeline(
    tmp_path: Path,
) -> tuple[BusinessDataset, CleaningOutcome, AnalysisResult, VisualizationResult]:
    csv_file = tmp_path / "sales.csv"
    csv_file.write_text(_CSV_CONTENT)

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
    visualization_service = VisualizationService(
        ingestion_service, ChartRecommendationEngine(default_generators(aggregation_engine)), LayoutEngine()
    )

    dataset = ingestion_service.ingest(str(csv_file), dataset_name="sales.csv")
    outcome = cleaning_service.clean(dataset)
    analysis_result = analysis_service.analyze(outcome)
    visualization_result = visualization_service.generate(analysis_result, dataset=outcome.dataset)
    return dataset, outcome, analysis_result, visualization_result


def test_build_report_stores_and_returns_a_valid_document(tmp_path: Path) -> None:
    _, outcome, analysis_result, visualization_result = _make_pipeline(tmp_path)
    service = _make_report_service()

    document = service.build_report(
        outcome.dataset,
        cleaning_outcome=outcome,
        analysis_result=analysis_result,
        visualization_result=visualization_result,
        template_type=ReportTemplateType.BUSINESS_REPORT,
    )

    assert document.report_id
    assert service.get_report(document.report_id) == document


def test_build_report_raises_when_a_required_section_would_be_missing(tmp_path: Path) -> None:
    _, outcome, _, _ = _make_pipeline(tmp_path)
    service = _make_report_service()

    with pytest.raises(ReportValidationFailedError) as excinfo:
        service.build_report(outcome.dataset, template_type=ReportTemplateType.TECHNICAL_REPORT)

    assert excinfo.value.detail is not None
    assert excinfo.value.detail.is_valid is False


def test_get_report_raises_not_found_for_an_unknown_id() -> None:
    service = _make_report_service()
    with pytest.raises(ReportNotFoundError):
        service.get_report("does-not-exist")


def test_list_reports_returns_most_recent_first(tmp_path: Path) -> None:
    _, outcome, analysis_result, visualization_result = _make_pipeline(tmp_path)
    service = _make_report_service()

    first = service.build_report(outcome.dataset, analysis_result=analysis_result, visualization_result=visualization_result)
    second = service.build_report(outcome.dataset, analysis_result=analysis_result, visualization_result=visualization_result)

    listed = service.list_reports()
    assert listed[0].report_id == second.report_id
    assert listed[1].report_id == first.report_id


def test_validate_report_never_raises_and_reports_problems(tmp_path: Path) -> None:
    _, outcome, _, _ = _make_pipeline(tmp_path)
    service = _make_report_service()
    document = ReportBuilder().build(outcome.dataset, template_type=ReportTemplateType.EXECUTIVE_SUMMARY)

    result = service.validate_report(document)

    assert result.is_valid is False
    assert any(issue.code == "missing_required_section" for issue in result.errors)


def test_export_report_as_json_round_trips(tmp_path: Path) -> None:
    _, outcome, analysis_result, visualization_result = _make_pipeline(tmp_path)
    service = _make_report_service()
    document = service.build_report(outcome.dataset, analysis_result=analysis_result, visualization_result=visualization_result)

    content = service.export_report(document.report_id, ReportExportFormat.JSON)

    assert isinstance(content, str)
    assert document.report_id in content


def test_export_report_as_markdown_returns_readable_text(tmp_path: Path) -> None:
    _, outcome, analysis_result, visualization_result = _make_pipeline(tmp_path)
    service = _make_report_service()
    document = service.build_report(outcome.dataset, analysis_result=analysis_result, visualization_result=visualization_result)

    content = service.export_report(document.report_id, ReportExportFormat.MARKDOWN)

    assert isinstance(content, str)
    assert content.startswith(f"# {document.title}")


def test_export_report_pdf_returns_a_placeholder(tmp_path: Path) -> None:
    _, outcome, analysis_result, visualization_result = _make_pipeline(tmp_path)
    service = _make_report_service()
    document = service.build_report(outcome.dataset, analysis_result=analysis_result, visualization_result=visualization_result)

    result = service.export_report(document.report_id, ReportExportFormat.PDF)

    assert isinstance(result, ExportPlaceholder)
    assert result.implemented is False


def test_export_report_raises_not_found_for_an_unknown_id() -> None:
    service = _make_report_service()
    with pytest.raises(ReportNotFoundError):
        service.export_report("does-not-exist", ReportExportFormat.JSON)
