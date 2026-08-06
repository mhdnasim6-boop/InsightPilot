"""Tests for ContextBuilder — intent-scoped fact extraction and reference tracking.

Fixtures are minimal, hand-built model instances (not a real ingested
dataset) so each test can precisely control edge cases like "applicable"
vs. "not applicable" sections — see ``tests/test_visualization_service.py``
for the alternative (real end-to-end pipeline) style used elsewhere.
"""

from datetime import UTC, datetime

from backend.adaptive.models.optimization_result import (
    OptimizationDecision,
    OptimizationDecisionCategory,
    OptimizationResult,
)
from backend.adaptive.models.planning_context import PlanningContext
from backend.analysis.models.anomaly import AnomalyAnalysisResult, ColumnAnomalyResult
from backend.analysis.models.correlation import (
    CorrelationAnalysisResult,
    CorrelationPair,
)
from backend.analysis.models.dataset_summary import DatasetSummary
from backend.analysis.models.insight import Insight
from backend.analysis.models.kpi import KPIResult, KPIType
from backend.analysis.models.result import AnalysisResult
from backend.analysis.models.statistics import ColumnStatistics, DescriptiveStatistics
from backend.analysis.models.trend import TrendAnalysisResult, TrendSeriesResult
from backend.chatbot.context.models import ChatContext
from backend.chatbot.retrieval.classifier import Intent
from backend.chatbot.retrieval.context_builder import ContextBuilder
from backend.ingestion.models.dataset import BusinessDataset
from backend.ingestion.models.source_type import SourceType
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.reflection.models.execution_review import ExecutionReview
from backend.reflection.models.recommendation import (
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
)
from backend.reflection.models.reflection_result import ReflectionResult
from backend.reflection.scoring.confidence_score import ConfidenceScore
from backend.reflection.scoring.efficiency_score import EfficiencyScore
from backend.reflection.scoring.execution_score import ExecutionScore
from backend.reporting.models.report_document import ReportDocument
from backend.reporting.sections.section import ReportSection
from backend.visualization.models.chart import ChartSpecification, ChartType
from backend.visualization.models.layout import Layout, LayoutType
from backend.visualization.models.result import VisualizationResult
from backend.workflows.models.workflow import Workflow
from backend.workflows.models.workflow_definition import WorkflowDefinition
from backend.workflows.models.workflow_status import WorkflowStatus
from backend.workflows.models.workflow_step import WorkflowStep


def _make_dataset() -> BusinessDataset:
    now = datetime.now(UTC)
    return BusinessDataset(
        dataset_id="d1",
        dataset_name="sales.csv",
        source_type=SourceType.CSV,
        source_location="/tmp/sales.csv",
        row_count=100,
        column_count=3,
        created_at=now,
        loaded_at=now,
    )


def _make_dataset_summary() -> DatasetSummary:
    return DatasetSummary(
        row_count=100,
        column_count=3,
        numeric_columns=["revenue"],
        categorical_columns=["region"],
        missing_values=0,
        memory_usage_bytes=1024,
        duplicate_count=0,
    )


def _make_analysis_result(
    *,
    kpis: list[KPIResult] | None = None,
    trends: TrendAnalysisResult | None = None,
    anomalies: AnomalyAnalysisResult | None = None,
    correlations: CorrelationAnalysisResult | None = None,
    insights: list[Insight] | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        analysis_id="a1",
        dataset_id="d1",
        analysis_timestamp=datetime.now(UTC),
        dataset_summary=_make_dataset_summary(),
        descriptive_statistics=DescriptiveStatistics(
            columns={"revenue": ColumnStatistics(column="revenue", mean=100.0, minimum=50.0, maximum=150.0)}
        ),
        kpis=kpis if kpis is not None else [KPIResult(name="Total Revenue", kpi_type=KPIType.SUM, value=1000.0)],
        trends=trends if trends is not None else TrendAnalysisResult(applicable=False, reason="No time column."),
        anomalies=anomalies if anomalies is not None else AnomalyAnalysisResult(applicable=False, reason="No numeric columns."),
        correlations=correlations
        if correlations is not None
        else CorrelationAnalysisResult(applicable=False, reason="Fewer than two numeric columns."),
        insights=insights if insights is not None else [],
        execution_time=0.01,
    )


def _make_visualization_result(charts: list[ChartSpecification] | None = None) -> VisualizationResult:
    charts = charts if charts is not None else [
        ChartSpecification(chart_id="c1", title="Revenue by Region", chart_type=ChartType.BAR, description="A bar chart.")
    ]
    return VisualizationResult(
        visualization_id="v1",
        analysis_id="a1",
        charts=charts,
        layout=Layout(layout_type=LayoutType.DETAILED_ANALYSIS, sections=[]),
        recommendations=["Consider a bar chart to compare regions."],
        execution_time=0.01,
    )


def _make_execution_plan() -> ExecutionPlan:
    now = datetime.now(UTC)
    return ExecutionPlan(
        plan_id="p1",
        goal="Clean and analyze the dataset.",
        status=PlanStatus.DRAFT,
        confidence=0.9,
        steps=[ExecutionStep(step_id="s1", name="Clean data", node_name="cleaning")],
        created_at=now,
        updated_at=now,
    )


def _make_report() -> ReportDocument:
    return ReportDocument(
        report_id="r1", title="Sales Report", generated_at=datetime.now(UTC),
        sections=[ReportSection(section_id="overview", title="Overview", order=0)],
    )


def _make_workflow() -> Workflow:
    now = datetime.now(UTC)
    return Workflow(
        workflow_id="w1",
        definition=WorkflowDefinition(
            name="Sales Pipeline", description="Cleans and analyzes sales data.",
            steps=[WorkflowStep(step_id="s1", name="Clean data", node_name="cleaning")],
        ),
        status=WorkflowStatus.READY, created_at=now, updated_at=now,
    )


def _make_reflection() -> ReflectionResult:
    return ReflectionResult(
        reflection_id="ref1", plan_id="p1", trace_id="t1",
        review=ExecutionReview(
            overall_success=True,
            execution_score=ExecutionScore(value=90.0, label="excellent"),
            efficiency_score=EfficiencyScore(value=80.0, label="good"),
            confidence_score=ConfidenceScore(value=85.0, label="good"),
            strengths=["Every step completed on the first attempt."],
            weaknesses=["Approval wait time was high."],
            recommendations=[
                Recommendation(
                    recommendation_id="rec1", category=RecommendationCategory.APPROVAL_POLICY,
                    message="Consider a less strict approval policy.", priority=RecommendationPriority.MEDIUM,
                    reason="Approval wait dominated total duration.",
                )
            ],
        ),
        generated_at=datetime.now(UTC),
    )


def _make_optimization() -> OptimizationResult:
    now = datetime.now(UTC)
    plan = ExecutionPlan(plan_id="p1", goal="Clean and analyze the dataset.", status=PlanStatus.DRAFT, created_at=now, updated_at=now)
    return OptimizationResult(
        optimization_id="opt1", plan_id="p1", original_plan=plan, optimized_plan=plan,
        decisions=[
            OptimizationDecision(
                decision_id="d1", category=OptimizationDecisionCategory.SKIP_STEP, applied=True,
                message="Skipped an unnecessary cleaning step.", reason="No downstream step depends on it.",
                evidence_count=3,
            )
        ],
        planning_context=PlanningContext(), generated_at=now,
    )


def test_summary_uses_analysis_result_when_present() -> None:
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result())
    retrieved = ContextBuilder().build(context, Intent.SUMMARY)

    assert "100 rows" in retrieved.facts_text
    assert retrieved.referenced_kpis == ["Total Revenue"]
    assert retrieved.referenced_datasets == []  # no selected_dataset in this context


def test_summary_falls_back_to_dataset_when_no_analysis() -> None:
    context = ChatContext(session_id="s1", selected_dataset=_make_dataset())
    retrieved = ContextBuilder().build(context, Intent.SUMMARY)

    assert "sales.csv" in retrieved.facts_text
    assert "No analysis has been run yet" in retrieved.facts_text
    assert retrieved.referenced_datasets == ["sales.csv"]


def test_summary_with_nothing_at_all() -> None:
    context = ChatContext(session_id="s1")
    retrieved = ContextBuilder().build(context, Intent.SUMMARY)

    assert "No dataset has been uploaded yet." in retrieved.facts_text


def test_kpi_references_every_kpi_name() -> None:
    kpis = [
        KPIResult(name="Total Revenue", kpi_type=KPIType.SUM, value=1000.0),
        KPIResult(name="Average Revenue", kpi_type=KPIType.AVERAGE, value=100.0),
    ]
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result(kpis=kpis))
    retrieved = ContextBuilder().build(context, Intent.KPI)

    assert retrieved.referenced_kpis == ["Total Revenue", "Average Revenue"]
    assert "1000.0" in retrieved.facts_text


def test_trend_not_applicable_gives_honest_reason_not_invented_numbers() -> None:
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result())
    retrieved = ContextBuilder().build(context, Intent.TREND)

    assert "No time column." in retrieved.facts_text
    assert retrieved.referenced_kpis == []


def test_trend_applicable_reports_series() -> None:
    trends = TrendAnalysisResult(
        applicable=True,
        time_column="date",
        window=3,
        series=[TrendSeriesResult(column="revenue", growth_rate=12.5)],
    )
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result(trends=trends))
    retrieved = ContextBuilder().build(context, Intent.TREND)

    assert "revenue" in retrieved.facts_text
    assert "12.5" in retrieved.facts_text


def test_trend_includes_only_trend_category_insights() -> None:
    insights = [
        Insight(category="trend", message="Revenue is trending up."),
        Insight(category="anomaly", message="West revenue spiked."),
    ]
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result(insights=insights))
    retrieved = ContextBuilder().build(context, Intent.TREND)

    assert retrieved.referenced_insights == ["Revenue is trending up."]


def test_anomaly_not_applicable() -> None:
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result())
    retrieved = ContextBuilder().build(context, Intent.ANOMALY)

    assert "No numeric columns." in retrieved.facts_text


def test_anomaly_applicable_reports_outlier_counts() -> None:
    anomalies = AnomalyAnalysisResult(
        applicable=True,
        columns=[ColumnAnomalyResult(column="revenue", zscore_outlier_count=2, zscore_outlier_percentage=5.0)],
    )
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result(anomalies=anomalies))
    retrieved = ContextBuilder().build(context, Intent.ANOMALY)

    assert "revenue" in retrieved.facts_text
    assert "2 Z-score outliers" in retrieved.facts_text


def test_correlation_applicable_reports_strong_pairs() -> None:
    correlations = CorrelationAnalysisResult(
        applicable=True,
        strong_positive=[CorrelationPair(column_a="revenue", column_b="cost", pearson=0.95)],
    )
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result(correlations=correlations))
    retrieved = ContextBuilder().build(context, Intent.CORRELATION)

    assert "revenue and cost" in retrieved.facts_text
    assert "0.95" in retrieved.facts_text


def test_comparison_falls_back_to_descriptive_statistics_when_correlations_not_applicable() -> None:
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result())
    retrieved = ContextBuilder().build(context, Intent.COMPARISON)

    assert "revenue" in retrieved.facts_text
    assert "100.0" in retrieved.facts_text  # the mean, from ColumnStatistics


def test_visualization_references_shown_chart_ids_only() -> None:
    charts = [
        ChartSpecification(chart_id="c1", title="Revenue by Region", chart_type=ChartType.BAR),
        ChartSpecification(chart_id="c2", title="Revenue Trend", chart_type=ChartType.LINE),
    ]
    context = ChatContext(session_id="s1", visualization_result=_make_visualization_result(charts=charts))
    retrieved = ContextBuilder().build(context, Intent.VISUALIZATION)

    assert retrieved.referenced_charts == ["c1", "c2"]
    assert "Revenue by Region" in retrieved.facts_text


def test_planning_reports_goal_status_and_steps() -> None:
    context = ChatContext(session_id="s1", execution_plan=_make_execution_plan())
    retrieved = ContextBuilder().build(context, Intent.PLANNING)

    assert "Clean and analyze the dataset." in retrieved.facts_text
    assert "Clean data" in retrieved.facts_text
    assert "draft" in retrieved.facts_text


def test_general_uses_same_broad_context_as_summary() -> None:
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result())
    retrieved = ContextBuilder().build(context, Intent.GENERAL)

    assert retrieved.referenced_kpis == ["Total Revenue"]


def test_referenced_datasets_populated_whenever_dataset_selected_regardless_of_intent() -> None:
    context = ChatContext(session_id="s1", selected_dataset=_make_dataset(), analysis_result=_make_analysis_result())
    retrieved = ContextBuilder().build(context, Intent.KPI)

    assert retrieved.referenced_datasets == ["sales.csv"]


def test_summary_surfaces_cleaning_outcome_when_present() -> None:
    from backend.cleaning.models.outcome import CleaningOutcome
    from backend.cleaning.models.profile import DatasetProfile
    from backend.cleaning.models.result import CleaningResult

    now = datetime.now(UTC)
    outcome = CleaningOutcome(
        dataset=_make_dataset(),
        result=CleaningResult(
            cleaning_id="cl1",
            dataset_id="d1",
            rows_before=105,
            rows_after=100,
            columns_before=3,
            columns_after=3,
            missing_values_before=5,
            missing_values_after=0,
            duplicates_removed=5,
            summary="Removed 5 duplicate rows.",
            quality_score=100.0,
            created_at=now,
        ),
        profile=DatasetProfile(dataset_id="d1", generated_at=now, row_count=100, column_count=3, memory_usage_bytes=1024),
    )
    context = ChatContext(session_id="s1", cleaning_outcome=outcome, analysis_result=_make_analysis_result())
    retrieved = ContextBuilder().build(context, Intent.SUMMARY)

    assert "Removed 5 duplicate rows." in retrieved.facts_text
    assert "5 duplicates removed" in retrieved.facts_text


def test_report_reports_title_and_sections() -> None:
    context = ChatContext(session_id="s1", report_document=_make_report())
    retrieved = ContextBuilder().build(context, Intent.REPORT)

    assert "Sales Report" in retrieved.facts_text
    assert "Overview" in retrieved.facts_text
    assert retrieved.metadata == {"report_id": "r1"}


def test_workflow_reports_name_status_and_steps() -> None:
    context = ChatContext(session_id="s1", workflow=_make_workflow())
    retrieved = ContextBuilder().build(context, Intent.WORKFLOW)

    assert "Sales Pipeline" in retrieved.facts_text
    assert "ready" in retrieved.facts_text
    assert "Clean data" in retrieved.facts_text
    assert retrieved.metadata == {"workflow_id": "w1"}


def test_reflection_reports_scores_strengths_and_recommendations() -> None:
    context = ChatContext(session_id="s1", reflection_result=_make_reflection())
    retrieved = ContextBuilder().build(context, Intent.REFLECTION)

    assert "90/100" in retrieved.facts_text
    assert "Every step completed on the first attempt." in retrieved.facts_text
    assert "Consider a less strict approval policy." in retrieved.facts_text
    assert retrieved.metadata == {"reflection_id": "ref1"}


def test_optimization_reports_goal_and_decisions() -> None:
    context = ChatContext(session_id="s1", optimization_result=_make_optimization())
    retrieved = ContextBuilder().build(context, Intent.OPTIMIZATION)

    assert "Clean and analyze the dataset." in retrieved.facts_text
    assert "Skipped an unnecessary cleaning step." in retrieved.facts_text
    assert "applied" in retrieved.facts_text
    assert retrieved.metadata == {"optimization_id": "opt1"}


def test_metadata_is_empty_for_intents_without_a_deep_link() -> None:
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result())
    retrieved = ContextBuilder().build(context, Intent.SUMMARY)

    assert retrieved.metadata == {}
