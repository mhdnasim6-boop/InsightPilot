"""Tests for ContextValidator — the pre-flight hallucination-prevention gate.

Every "answerable=False" case here must be decided *before* any AI call
is made; :func:`test_chatbot_service.py` separately confirms ChatService
actually honors that by never invoking AIService on the refusal path.
"""

from datetime import UTC, datetime

from backend.adaptive.models.optimization_result import OptimizationResult
from backend.adaptive.models.planning_context import PlanningContext
from backend.analysis.models.anomaly import AnomalyAnalysisResult
from backend.analysis.models.correlation import CorrelationAnalysisResult
from backend.analysis.models.dataset_summary import DatasetSummary
from backend.analysis.models.kpi import KPIResult, KPIType
from backend.analysis.models.result import AnalysisResult
from backend.analysis.models.statistics import DescriptiveStatistics
from backend.analysis.models.trend import TrendAnalysisResult
from backend.chatbot.context.models import ChatContext
from backend.chatbot.retrieval.classifier import Intent
from backend.chatbot.validation.answerability import ContextValidator
from backend.ingestion.models.dataset import BusinessDataset
from backend.ingestion.models.source_type import SourceType
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.reflection.models.execution_review import ExecutionReview
from backend.reflection.models.reflection_result import ReflectionResult
from backend.reflection.scoring.confidence_score import ConfidenceScore
from backend.reflection.scoring.efficiency_score import EfficiencyScore
from backend.reflection.scoring.execution_score import ExecutionScore
from backend.reporting.models.report_document import ReportDocument
from backend.visualization.models.chart import ChartSpecification, ChartType
from backend.visualization.models.layout import Layout, LayoutType
from backend.visualization.models.result import VisualizationResult
from backend.workflows.models.workflow import Workflow
from backend.workflows.models.workflow_definition import WorkflowDefinition
from backend.workflows.models.workflow_status import WorkflowStatus


def _make_dataset() -> BusinessDataset:
    now = datetime.now(UTC)
    return BusinessDataset(
        dataset_id="d1", dataset_name="sales.csv", source_type=SourceType.CSV, source_location="/tmp/sales.csv",
        row_count=100, column_count=3, created_at=now, loaded_at=now,
    )


def _make_analysis_result(*, kpis: list[KPIResult] | None = None, trends_applicable: bool = True) -> AnalysisResult:
    return AnalysisResult(
        analysis_id="a1",
        dataset_id="d1",
        analysis_timestamp=datetime.now(UTC),
        dataset_summary=DatasetSummary(
            row_count=100, column_count=3, missing_values=0, duplicate_count=0, memory_usage_bytes=1024
        ),
        descriptive_statistics=DescriptiveStatistics(),
        kpis=kpis if kpis is not None else [KPIResult(name="Total Revenue", kpi_type=KPIType.SUM, value=1000.0)],
        trends=TrendAnalysisResult(applicable=trends_applicable, reason=None if trends_applicable else "No time column."),
        anomalies=AnomalyAnalysisResult(applicable=True),
        correlations=CorrelationAnalysisResult(applicable=True),
        execution_time=0.01,
    )


def _make_report() -> ReportDocument:
    return ReportDocument(report_id="r1", title="Sales Report", generated_at=datetime.now(UTC))


def _make_workflow() -> Workflow:
    now = datetime.now(UTC)
    return Workflow(
        workflow_id="w1", definition=WorkflowDefinition(name="Sales Pipeline"),
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
        ),
        generated_at=datetime.now(UTC),
    )


def _make_optimization() -> OptimizationResult:
    now = datetime.now(UTC)
    plan = ExecutionPlan(plan_id="p1", goal="Clean data.", status=PlanStatus.DRAFT, created_at=now, updated_at=now)
    return OptimizationResult(
        optimization_id="opt1", plan_id="p1", original_plan=plan, optimized_plan=plan,
        planning_context=PlanningContext(), generated_at=now,
    )


def test_general_is_always_answerable_even_with_empty_context() -> None:
    validator = ContextValidator()
    result = validator.check(ChatContext(session_id="s1"), Intent.GENERAL)

    assert result.answerable is True
    assert result.is_partial is False


def test_summary_unanswerable_with_no_dataset_and_no_analysis() -> None:
    validator = ContextValidator()
    result = validator.check(ChatContext(session_id="s1"), Intent.SUMMARY)

    assert result.answerable is False
    assert result.reason is not None


def test_summary_answerable_with_only_a_selected_dataset() -> None:
    validator = ContextValidator()
    context = ChatContext(session_id="s1", selected_dataset=_make_dataset())
    result = validator.check(context, Intent.SUMMARY)

    assert result.answerable is True


def test_kpi_unanswerable_without_analysis_result() -> None:
    validator = ContextValidator()
    result = validator.check(ChatContext(session_id="s1"), Intent.KPI)

    assert result.answerable is False
    assert "hasn't been analyzed" in (result.reason or "")


def test_kpi_unanswerable_when_analysis_has_no_kpis() -> None:
    validator = ContextValidator()
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result(kpis=[]))
    result = validator.check(context, Intent.KPI)

    assert result.answerable is False
    assert "No KPIs" in (result.reason or "")


def test_kpi_answerable_when_kpis_present() -> None:
    validator = ContextValidator()
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result())
    result = validator.check(context, Intent.KPI)

    assert result.answerable is True
    assert result.is_partial is False


def test_trend_partial_when_analysis_present_but_not_applicable() -> None:
    validator = ContextValidator()
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result(trends_applicable=False))
    result = validator.check(context, Intent.TREND)

    assert result.answerable is True
    assert result.is_partial is True


def test_trend_not_partial_when_applicable() -> None:
    validator = ContextValidator()
    context = ChatContext(session_id="s1", analysis_result=_make_analysis_result(trends_applicable=True))
    result = validator.check(context, Intent.TREND)

    assert result.answerable is True
    assert result.is_partial is False


def test_visualization_unanswerable_with_no_charts() -> None:
    validator = ContextValidator()
    viz = VisualizationResult(
        visualization_id="v1", analysis_id="a1", charts=[],
        layout=Layout(layout_type=LayoutType.DETAILED_ANALYSIS, sections=[]), execution_time=0.01,
    )
    context = ChatContext(session_id="s1", visualization_result=viz)
    result = validator.check(context, Intent.VISUALIZATION)

    assert result.answerable is False


def test_visualization_answerable_with_charts() -> None:
    validator = ContextValidator()
    viz = VisualizationResult(
        visualization_id="v1", analysis_id="a1",
        charts=[ChartSpecification(chart_id="c1", title="Revenue", chart_type=ChartType.BAR)],
        layout=Layout(layout_type=LayoutType.DETAILED_ANALYSIS, sections=[]), execution_time=0.01,
    )
    context = ChatContext(session_id="s1", visualization_result=viz)
    result = validator.check(context, Intent.VISUALIZATION)

    assert result.answerable is True


def test_planning_unanswerable_without_execution_plan() -> None:
    validator = ContextValidator()
    result = validator.check(ChatContext(session_id="s1"), Intent.PLANNING)

    assert result.answerable is False
    assert "No execution plan" in (result.reason or "")


def test_planning_answerable_with_execution_plan() -> None:
    validator = ContextValidator()
    now = datetime.now(UTC)
    plan = ExecutionPlan(plan_id="p1", goal="Clean data.", status=PlanStatus.DRAFT, created_at=now, updated_at=now)
    context = ChatContext(session_id="s1", execution_plan=plan)
    result = validator.check(context, Intent.PLANNING)

    assert result.answerable is True


def test_report_unanswerable_without_report_document() -> None:
    validator = ContextValidator()
    result = validator.check(ChatContext(session_id="s1"), Intent.REPORT)

    assert result.answerable is False
    assert "No report" in (result.reason or "")


def test_report_answerable_with_report_document() -> None:
    validator = ContextValidator()
    context = ChatContext(session_id="s1", report_document=_make_report())
    result = validator.check(context, Intent.REPORT)

    assert result.answerable is True


def test_workflow_unanswerable_without_workflow() -> None:
    validator = ContextValidator()
    result = validator.check(ChatContext(session_id="s1"), Intent.WORKFLOW)

    assert result.answerable is False
    assert "No workflow" in (result.reason or "")


def test_workflow_answerable_with_workflow() -> None:
    validator = ContextValidator()
    context = ChatContext(session_id="s1", workflow=_make_workflow())
    result = validator.check(context, Intent.WORKFLOW)

    assert result.answerable is True


def test_reflection_unanswerable_without_reflection_result() -> None:
    validator = ContextValidator()
    result = validator.check(ChatContext(session_id="s1"), Intent.REFLECTION)

    assert result.answerable is False
    assert "No reflection" in (result.reason or "")


def test_reflection_answerable_with_reflection_result() -> None:
    validator = ContextValidator()
    context = ChatContext(session_id="s1", reflection_result=_make_reflection())
    result = validator.check(context, Intent.REFLECTION)

    assert result.answerable is True


def test_optimization_unanswerable_without_optimization_result() -> None:
    validator = ContextValidator()
    result = validator.check(ChatContext(session_id="s1"), Intent.OPTIMIZATION)

    assert result.answerable is False
    assert "No plan optimization" in (result.reason or "")


def test_optimization_answerable_with_optimization_result() -> None:
    validator = ContextValidator()
    context = ChatContext(session_id="s1", optimization_result=_make_optimization())
    result = validator.check(context, Intent.OPTIMIZATION)

    assert result.answerable is True
