"""Integration tests for ReportBuilder: build a report from a real
ingested / cleaned / analyzed / visualized dataset end to end.
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
from backend.cleaning.models.outcome import CleaningOutcome
from backend.cleaning.profiling.profiler import DatasetProfilingService
from backend.ingestion.metadata.extractor import MetadataExtractor
from backend.ingestion.models.dataset import BusinessDataset
from backend.ingestion.registry.dataframe_store import DataFrameStore
from backend.ingestion.registry.loader_registry import LoaderRegistry
from backend.ingestion.validators.validator import DatasetValidator
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.sections.content_blocks import (
    ChartReferenceBlock,
    KPIGridBlock,
    TableBlock,
)
from backend.reporting.templates.report_template import ReportTemplateType, get_template
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


def test_build_with_all_inputs_follows_the_templates_section_order(tmp_path: Path) -> None:
    _, outcome, analysis_result, visualization_result = _make_pipeline(tmp_path)

    document = ReportBuilder().build(
        outcome.dataset,
        cleaning_outcome=outcome,
        analysis_result=analysis_result,
        visualization_result=visualization_result,
        template_type=ReportTemplateType.BUSINESS_REPORT,
    )

    template = get_template(ReportTemplateType.BUSINESS_REPORT)
    expected_order = [kind.value for kind in template.section_order]
    actual_order = [section.section_id for section in document.sections]
    assert actual_order == [s for s in expected_order if s in actual_order]
    assert [section.order for section in document.sections] == list(range(len(document.sections)))


def test_build_populates_kpis_and_charts_from_real_engine_output(tmp_path: Path) -> None:
    _, outcome, analysis_result, visualization_result = _make_pipeline(tmp_path)

    document = ReportBuilder().build(
        outcome.dataset,
        cleaning_outcome=outcome,
        analysis_result=analysis_result,
        visualization_result=visualization_result,
    )

    kpis_section = next(s for s in document.sections if s.section_id == "kpis")
    kpi_grid = kpis_section.content_blocks[0]
    assert isinstance(kpi_grid, KPIGridBlock)
    assert {kpi.name for kpi in kpi_grid.kpis} == {kpi.name for kpi in analysis_result.kpis}

    charts_section = next(s for s in document.sections if s.section_id == "charts")
    referenced_ids = {block.chart_id for block in charts_section.content_blocks if isinstance(block, ChartReferenceBlock)}
    assert referenced_ids == {chart.chart_id for chart in visualization_result.charts}
    assert set(charts_section.charts) == referenced_ids


def test_build_produces_a_document_that_passes_its_own_validation(tmp_path: Path) -> None:
    _, outcome, analysis_result, visualization_result = _make_pipeline(tmp_path)

    document = ReportBuilder().build(
        outcome.dataset,
        cleaning_outcome=outcome,
        analysis_result=analysis_result,
        visualization_result=visualization_result,
        template_type=ReportTemplateType.TECHNICAL_REPORT,
    )

    result = ReportValidator().validate(document, analysis_result, visualization_result)
    assert result.is_valid is True, result.errors


def test_appendix_does_not_repeat_the_analysis_sections_correlation_table(tmp_path: Path) -> None:
    _, outcome, analysis_result, visualization_result = _make_pipeline(tmp_path)

    document = ReportBuilder().build(
        outcome.dataset,
        cleaning_outcome=outcome,
        analysis_result=analysis_result,
        visualization_result=visualization_result,
        template_type=ReportTemplateType.TECHNICAL_REPORT,
    )

    analysis_section = next(s for s in document.sections if s.section_id == "analysis")
    analysis_captions = {b.caption for b in analysis_section.content_blocks if isinstance(b, TableBlock)}

    appendix = document.appendices[0]
    appendix_captions = {b.caption for b in appendix.content_blocks if isinstance(b, TableBlock)}

    assert analysis_captions.isdisjoint(appendix_captions)
    assert "Full Pearson correlation matrix" in appendix_captions
    assert "Sample rows" in appendix_captions


def test_table_of_contents_covers_every_section_and_appendix(tmp_path: Path) -> None:
    _, outcome, analysis_result, visualization_result = _make_pipeline(tmp_path)

    document = ReportBuilder().build(
        outcome.dataset,
        cleaning_outcome=outcome,
        analysis_result=analysis_result,
        visualization_result=visualization_result,
        template_type=ReportTemplateType.TECHNICAL_REPORT,
    )

    toc_ids = [entry.section_id for entry in document.table_of_contents]
    assert toc_ids == [s.section_id for s in document.sections] + [a.section_id for a in document.appendices]


def test_title_defaults_to_dataset_name_and_can_be_overridden(tmp_path: Path) -> None:
    dataset, outcome, _, _ = _make_pipeline(tmp_path)

    default_titled = ReportBuilder().build(outcome.dataset)
    assert default_titled.title == f"{dataset.dataset_name} Report"

    custom_titled = ReportBuilder().build(
        outcome.dataset, title="Board Deck", subtitle="Q1 review", author="Finance Team"
    )
    assert custom_titled.title == "Board Deck"
    assert custom_titled.subtitle == "Q1 review"
    assert custom_titled.author == "Finance Team"


def test_metadata_records_template_type_and_dataset_id(tmp_path: Path) -> None:
    _, outcome, _, _ = _make_pipeline(tmp_path)

    document = ReportBuilder().build(
        outcome.dataset, template_type=ReportTemplateType.DATA_QUALITY_REPORT, cleaning_outcome=outcome
    )

    assert document.metadata["template_type"] == "data_quality_report"
    assert document.metadata["dataset_id"] == outcome.dataset.dataset_id


def test_missing_analysis_result_gracefully_omits_dependent_sections(tmp_path: Path) -> None:
    dataset, _, _, _ = _make_pipeline(tmp_path)

    document = ReportBuilder().build(dataset, template_type=ReportTemplateType.EXECUTIVE_SUMMARY)

    assert [s.section_id for s in document.sections] == ["overview"]

    result = ReportValidator().validate(document)
    assert result.is_valid is False
    assert any(issue.code == "missing_required_section" for issue in result.errors)
