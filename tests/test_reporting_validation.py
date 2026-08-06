"""Tests for ReportValidator: each check exercised individually against a
real, valid document produced by ReportBuilder from a real analyzed and
visualized dataset — not hand-built fixtures for the domain objects.
"""

from pathlib import Path

from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.anomalies.engine import AnomalyEngine
from backend.analysis.correlations.engine import CorrelationEngine
from backend.analysis.insights.engine import InsightEngine
from backend.analysis.kpis.engine import KPIEngine
from backend.analysis.models.result import AnalysisResult
from backend.analysis.statistics.engine import DescriptiveStatisticsEngine
from backend.analysis.trends.engine import TrendEngine
from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.models.report_document import ReportDocument
from backend.reporting.sections.content_blocks import KPIGridBlock, ReportKPIEntry
from backend.reporting.templates.report_template import ReportTemplateType
from backend.reporting.validation.validator import ReportValidator
from backend.services.analysis_service import AnalysisService
from backend.services.cleaning_service import CleaningService
from backend.services.ingestion_service import IngestionService
from backend.services.visualization_service import VisualizationService
from backend.visualization.charts.registry import default_generators
from backend.visualization.layouts.engine import LayoutEngine
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


def _build_valid_report(tmp_path: Path) -> tuple[ReportDocument, AnalysisResult, VisualizationResult]:
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

    dataset = ingestion_service.ingest(str(csv_file))
    outcome = cleaning_service.clean(dataset)
    analysis_result = analysis_service.analyze(outcome)
    visualization_result = visualization_service.generate(analysis_result, dataset=outcome.dataset)

    document = ReportBuilder().build(
        outcome.dataset,
        cleaning_outcome=outcome,
        analysis_result=analysis_result,
        visualization_result=visualization_result,
        template_type=ReportTemplateType.BUSINESS_REPORT,
    )
    return document, analysis_result, visualization_result


def test_a_well_formed_document_is_valid(tmp_path: Path) -> None:
    document, analysis_result, visualization_result = _build_valid_report(tmp_path)

    result = ReportValidator().validate(document, analysis_result, visualization_result)

    assert result.is_valid is True
    assert result.errors == []


def test_no_sections_is_an_error(tmp_path: Path) -> None:
    document, _, _ = _build_valid_report(tmp_path)
    document.sections.clear()

    result = ReportValidator().validate(document)

    assert result.is_valid is False
    assert any(issue.code == "no_sections" for issue in result.errors)


def test_duplicate_section_order_is_an_error(tmp_path: Path) -> None:
    document, _, _ = _build_valid_report(tmp_path)
    document.sections[1].order = document.sections[0].order

    result = ReportValidator().validate(document)

    assert result.is_valid is False
    assert any(issue.code == "duplicate_section_order" for issue in result.errors)


def test_missing_required_section_is_an_error(tmp_path: Path) -> None:
    document, _, _ = _build_valid_report(tmp_path)
    assert document.metadata["template_type"] == "business_report"  # KPIS is required for this template
    document.sections = [s for s in document.sections if s.section_id != "kpis"]

    result = ReportValidator().validate(document)

    assert result.is_valid is False
    assert any(issue.code == "missing_required_section" for issue in result.errors)


def test_unknown_chart_reference_is_an_error_only_when_visualization_result_is_given(tmp_path: Path) -> None:
    document, analysis_result, visualization_result = _build_valid_report(tmp_path)
    charts_section = next(s for s in document.sections if s.section_id == "charts")
    charts_section.charts.append("chart-that-does-not-exist")

    without_source = ReportValidator().validate(document, analysis_result)
    assert without_source.is_valid is True  # nothing to compare against, so no complaint

    with_source = ReportValidator().validate(document, analysis_result, visualization_result)
    assert with_source.is_valid is False
    assert any(issue.code == "unknown_chart_reference" for issue in with_source.errors)


def test_unknown_kpi_reference_is_an_error_only_when_analysis_result_is_given(tmp_path: Path) -> None:
    document, analysis_result, visualization_result = _build_valid_report(tmp_path)
    kpis_section = next(s for s in document.sections if s.section_id == "kpis")
    kpi_grid = kpis_section.content_blocks[0]
    assert isinstance(kpi_grid, KPIGridBlock)
    kpi_grid.kpis.append(ReportKPIEntry(name="totally_fake_kpi", value=1))

    without_source = ReportValidator().validate(document, visualization_result=visualization_result)
    assert without_source.is_valid is True

    with_source = ReportValidator().validate(document, analysis_result, visualization_result)
    assert with_source.is_valid is False
    assert any(issue.code == "unknown_kpi_reference" for issue in with_source.errors)
