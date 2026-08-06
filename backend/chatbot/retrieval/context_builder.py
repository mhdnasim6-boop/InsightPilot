"""Builds a compact, intent-scoped fact block from a ``ChatContext``.

This is where hallucination prevention actually lives structurally: the
returned ``RetrievedContext.facts_text`` is the *only* dataset-derived
text that ever reaches a prompt, and ``referenced_*`` lists are computed
from exactly what was included here — never parsed back out of the
model's own response. The model cannot claim to reference a KPI, chart,
or insight that this module didn't already decide to show it.

Only already-computed sections of ``AnalysisResult``/``VisualizationResult``/
``ExecutionPlan`` are read — never a DataFrame, never
``BusinessDataset.sample_rows``.
"""

from typing import Any

from pydantic import BaseModel, Field

from backend.adaptive.models.optimization_result import OptimizationResult
from backend.analysis.models.anomaly import AnomalyAnalysisResult
from backend.analysis.models.correlation import CorrelationAnalysisResult
from backend.analysis.models.dataset_summary import DatasetSummary
from backend.analysis.models.insight import Insight
from backend.analysis.models.kpi import KPIResult
from backend.analysis.models.statistics import DescriptiveStatistics
from backend.analysis.models.trend import TrendAnalysisResult
from backend.chatbot.context.models import ChatContext
from backend.chatbot.retrieval.classifier import Intent
from backend.cleaning.models.outcome import CleaningOutcome
from backend.reflection.models.reflection_result import ReflectionResult
from backend.reporting.models.report_document import ReportDocument
from backend.visualization.models.chart import ChartSpecification
from backend.visualization.models.result import VisualizationResult
from backend.workflows.models.workflow import Workflow

_MAX_KPIS = 8
_MAX_INSIGHTS = 5
_MAX_CHARTS = 10
_MAX_RECOMMENDATIONS = 5
_MAX_DECISIONS = 8


class RetrievedContext(BaseModel):
    """The curated slice of ``ChatContext`` relevant to one classified intent."""

    intent: Intent
    facts_text: str
    referenced_kpis: list[str] = Field(default_factory=list)
    referenced_charts: list[str] = Field(default_factory=list)
    referenced_insights: list[str] = Field(default_factory=list)
    referenced_datasets: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    """A small, intent-specific deep-link id (``report_id``/``workflow_id``/
    ``reflection_id``/``optimization_id``) the frontend can use to render an
    "Open in <page>" action. Computed straight from ``context`` — never
    parsed out of the model's own answer, and never itself sent to the AI
    call (only ``facts_text`` is)."""


class ContextBuilder:
    """Extracts exactly the facts relevant to one intent from a ``ChatContext``."""

    def build(self, context: ChatContext, intent: Intent) -> RetrievedContext:
        """Return the curated, intent-scoped facts for ``context``."""
        facts_text, referenced_kpis, referenced_charts, referenced_insights = self._dispatch(context, intent)

        referenced_datasets = [context.selected_dataset.dataset_name] if context.selected_dataset else []

        return RetrievedContext(
            intent=intent,
            facts_text=facts_text,
            referenced_kpis=referenced_kpis,
            referenced_charts=referenced_charts,
            referenced_insights=referenced_insights,
            referenced_datasets=referenced_datasets,
            metadata=self._deep_link_metadata(context, intent),
        )

    def _deep_link_metadata(self, context: ChatContext, intent: Intent) -> dict[str, Any]:
        if intent == Intent.REPORT and context.report_document is not None:
            return {"report_id": context.report_document.report_id}
        if intent == Intent.WORKFLOW and context.workflow is not None:
            return {"workflow_id": context.workflow.workflow_id}
        if intent == Intent.REFLECTION and context.reflection_result is not None:
            return {"reflection_id": context.reflection_result.reflection_id}
        if intent == Intent.OPTIMIZATION and context.optimization_result is not None:
            return {"optimization_id": context.optimization_result.optimization_id}
        return {}

    def _dispatch(self, context: ChatContext, intent: Intent) -> tuple[str, list[str], list[str], list[str]]:
        handlers = {
            Intent.SUMMARY: self._build_summary,
            Intent.KPI: self._build_kpi,
            Intent.TREND: self._build_trend,
            Intent.COMPARISON: self._build_comparison,
            Intent.ANOMALY: self._build_anomaly,
            Intent.CORRELATION: self._build_correlation,
            Intent.EXPLANATION: self._build_explanation,
            Intent.VISUALIZATION: self._build_visualization,
            Intent.PLANNING: self._build_planning,
            Intent.REPORT: self._build_report,
            Intent.WORKFLOW: self._build_workflow,
            Intent.REFLECTION: self._build_reflection,
            Intent.OPTIMIZATION: self._build_optimization,
            Intent.GENERAL: self._build_summary,
        }
        return handlers[intent](context)

    # -- Per-intent extraction -------------------------------------------------

    def _build_summary(self, context: ChatContext) -> tuple[str, list[str], list[str], list[str]]:
        lines: list[str] = []
        referenced_kpis: list[str] = []
        referenced_insights: list[str] = []

        if context.cleaning_outcome is not None:
            lines.append(_render_cleaning_summary(context.cleaning_outcome))

        if context.analysis_result is not None:
            lines.append(_render_dataset_summary(context.analysis_result.dataset_summary))
            top_kpis = context.analysis_result.kpis[:_MAX_KPIS]
            if top_kpis:
                lines.append("Key metrics:")
                lines.extend(f"- {kpi.name}: {kpi.value}" for kpi in top_kpis)
                referenced_kpis = [kpi.name for kpi in top_kpis]
            top_insights = context.analysis_result.insights[:_MAX_INSIGHTS]
            if top_insights:
                lines.append("Notable findings:")
                lines.extend(f"- {insight.message}" for insight in top_insights)
                referenced_insights = [insight.message for insight in top_insights]
        elif context.selected_dataset is not None:
            dataset = context.selected_dataset
            lines.append(
                f"Dataset '{dataset.dataset_name}': {dataset.row_count} rows, "
                f"{dataset.column_count} columns. No analysis has been run yet."
            )
        else:
            lines.append("No dataset has been uploaded yet.")

        return "\n".join(lines), referenced_kpis, [], referenced_insights

    def _build_kpi(self, context: ChatContext) -> tuple[str, list[str], list[str], list[str]]:
        assert context.analysis_result is not None  # guaranteed by ContextValidator before this runs
        kpis = context.analysis_result.kpis
        return _render_kpi_lines(kpis), [kpi.name for kpi in kpis], [], []

    def _build_trend(self, context: ChatContext) -> tuple[str, list[str], list[str], list[str]]:
        assert context.analysis_result is not None
        trends = context.analysis_result.trends
        insights = _insights_by_category(context.analysis_result.insights, "trend")
        text = _render_trends(trends)
        if insights:
            text += "\nRelated findings:\n" + "\n".join(f"- {insight.message}" for insight in insights)
        return text, [], [], [insight.message for insight in insights]

    def _build_comparison(self, context: ChatContext) -> tuple[str, list[str], list[str], list[str]]:
        assert context.analysis_result is not None
        result = context.analysis_result
        lines = [_render_column_comparison(result.dataset_summary, result.descriptive_statistics)]
        if result.correlations.applicable:
            lines.append(_render_correlations(result.correlations))
        insights = _insights_by_category(result.insights, "correlation")
        if insights:
            lines.append("Related findings:\n" + "\n".join(f"- {insight.message}" for insight in insights))
        return "\n".join(lines), [], [], [insight.message for insight in insights]

    def _build_anomaly(self, context: ChatContext) -> tuple[str, list[str], list[str], list[str]]:
        assert context.analysis_result is not None
        anomalies = context.analysis_result.anomalies
        insights = _insights_by_category(context.analysis_result.insights, "anomaly")
        text = _render_anomalies(anomalies)
        if insights:
            text += "\nRelated findings:\n" + "\n".join(f"- {insight.message}" for insight in insights)
        return text, [], [], [insight.message for insight in insights]

    def _build_correlation(self, context: ChatContext) -> tuple[str, list[str], list[str], list[str]]:
        assert context.analysis_result is not None
        correlations = context.analysis_result.correlations
        insights = _insights_by_category(context.analysis_result.insights, "correlation")
        text = _render_correlations(correlations)
        if insights:
            text += "\nRelated findings:\n" + "\n".join(f"- {insight.message}" for insight in insights)
        return text, [], [], [insight.message for insight in insights]

    def _build_explanation(self, context: ChatContext) -> tuple[str, list[str], list[str], list[str]]:
        assert context.analysis_result is not None or context.selected_dataset is not None
        if context.analysis_result is None:
            return self._build_summary(context)

        result = context.analysis_result
        lines = [_render_dataset_summary(result.dataset_summary)]
        top_insights = result.insights[:_MAX_INSIGHTS]
        if top_insights:
            lines.append("Findings that may explain this:")
            lines.extend(f"- {insight.message}" for insight in top_insights)
        top_kpis = result.kpis[:_MAX_KPIS]
        if top_kpis:
            lines.append("Supporting metrics:")
            lines.extend(f"- {kpi.name}: {kpi.value}" for kpi in top_kpis)
        return (
            "\n".join(lines),
            [kpi.name for kpi in top_kpis],
            [],
            [insight.message for insight in top_insights],
        )

    def _build_visualization(self, context: ChatContext) -> tuple[str, list[str], list[str], list[str]]:
        assert context.visualization_result is not None
        charts = context.visualization_result.charts[:_MAX_CHARTS]
        text = _render_charts(charts, context.visualization_result)
        return text, [], [chart.chart_id for chart in charts], []

    def _build_planning(self, context: ChatContext) -> tuple[str, list[str], list[str], list[str]]:
        assert context.execution_plan is not None
        plan = context.execution_plan
        lines = [f"Goal: {plan.goal or 'Not stated.'}", f"Status: {plan.status.value}"]
        if plan.confidence is not None:
            lines.append(f"Confidence: {plan.confidence:.0%}")
        if plan.steps:
            lines.append("Steps:")
            lines.extend(
                f"- {index}. {step.name} (node: {step.node_name}, status: {step.status.value})"
                for index, step in enumerate(plan.steps, start=1)
            )
        else:
            lines.append("This plan has no steps.")
        return "\n".join(lines), [], [], []

    def _build_report(self, context: ChatContext) -> tuple[str, list[str], list[str], list[str]]:
        assert context.report_document is not None
        return _render_report(context.report_document), [], [], []

    def _build_workflow(self, context: ChatContext) -> tuple[str, list[str], list[str], list[str]]:
        assert context.workflow is not None
        return _render_workflow(context.workflow), [], [], []

    def _build_reflection(self, context: ChatContext) -> tuple[str, list[str], list[str], list[str]]:
        assert context.reflection_result is not None
        return _render_reflection(context.reflection_result), [], [], []

    def _build_optimization(self, context: ChatContext) -> tuple[str, list[str], list[str], list[str]]:
        assert context.optimization_result is not None
        return _render_optimization(context.optimization_result), [], [], []


# -- Pure rendering helpers ---------------------------------------------------


def _render_dataset_summary(summary: DatasetSummary) -> str:
    return (
        f"Dataset shape: {summary.row_count} rows, {summary.column_count} columns "
        f"({summary.missing_values} missing values, {summary.duplicate_count} duplicate rows). "
        f"Numeric columns: {', '.join(summary.numeric_columns) or 'none'}. "
        f"Categorical columns: {', '.join(summary.categorical_columns) or 'none'}."
    )


def _render_kpi_lines(kpis: list[KPIResult]) -> str:
    if not kpis:
        return "No KPIs have been computed for this dataset."
    return "\n".join(f"- {kpi.name}: {kpi.value}" for kpi in kpis)


def _render_cleaning_summary(cleaning_outcome: CleaningOutcome) -> str:
    result = cleaning_outcome.result
    return (
        f"Cleaning: {result.summary} (rows {result.rows_before} -> {result.rows_after}, "
        f"{result.duplicates_removed} duplicates removed, quality score {result.quality_score})."
    )


def _render_trends(trends: TrendAnalysisResult) -> str:
    if not trends.applicable:
        return f"Trend analysis is not applicable to this dataset: {trends.reason}"
    if not trends.series:
        return "Trend analysis found no numeric series to report on."
    lines = [f"Time column: {trends.time_column}, rolling window: {trends.window}."]
    lines.extend(
        f"- {series.column}: growth rate {series.growth_rate}"
        if series.growth_rate is not None
        else f"- {series.column}: growth rate unavailable"
        for series in trends.series
    )
    return "\n".join(lines)


def _render_anomalies(anomalies: AnomalyAnalysisResult) -> str:
    if not anomalies.applicable:
        return f"Anomaly detection is not applicable to this dataset: {anomalies.reason}"
    if not anomalies.columns:
        return "No anomalies were detected in this dataset."
    lines = ["Outliers detected (Z-score and IQR methods):"]
    lines.extend(
        f"- {column.column}: {column.zscore_outlier_count} Z-score outliers "
        f"({column.zscore_outlier_percentage}%), {column.iqr_outlier_count} IQR outliers "
        f"({column.iqr_outlier_percentage}%)"
        for column in anomalies.columns
    )
    return "\n".join(lines)


def _render_correlations(correlations: CorrelationAnalysisResult) -> str:
    if not correlations.applicable:
        return f"Correlation analysis is not applicable to this dataset: {correlations.reason}"
    lines = []
    if correlations.strong_positive:
        lines.append("Strong positive correlations:")
        lines.extend(f"- {pair.column_a} and {pair.column_b}: {pair.pearson}" for pair in correlations.strong_positive)
    if correlations.strong_negative:
        lines.append("Strong negative correlations:")
        lines.extend(f"- {pair.column_a} and {pair.column_b}: {pair.pearson}" for pair in correlations.strong_negative)
    if not lines:
        lines.append("No strong correlations were found between columns.")
    return "\n".join(lines)


def _render_column_comparison(summary: DatasetSummary, statistics: DescriptiveStatistics) -> str:
    if not statistics.columns:
        return _render_dataset_summary(summary)
    lines = ["Column comparison (mean / min / max):"]
    lines.extend(
        f"- {name}: {stats.mean} / {stats.minimum} / {stats.maximum}" for name, stats in statistics.columns.items()
    )
    return "\n".join(lines)


def _render_charts(charts: list[ChartSpecification], visualization_result: VisualizationResult) -> str:
    if not charts:
        return "No charts have been generated for this dataset yet."
    lines = [f"- {chart.title} ({chart.chart_type.value}): {chart.description or 'no description'}" for chart in charts]
    if visualization_result.recommendations:
        lines.append("Recommendations:")
        lines.extend(f"- {reco}" for reco in visualization_result.recommendations)
    return "\n".join(lines)


def _insights_by_category(insights: list[Insight], category: str) -> list[Insight]:
    return [insight for insight in insights if insight.category == category][:_MAX_INSIGHTS]


def _render_report(report: ReportDocument) -> str:
    lines = [f"Report: {report.title}"]
    if report.subtitle:
        lines.append(f"Subtitle: {report.subtitle}")
    lines.append(f"Generated: {report.generated_at.isoformat()} (theme: {report.theme}, version: {report.version}).")
    if report.sections:
        lines.append("Sections:")
        lines.extend(f"- {section.title}" for section in report.sections)
    else:
        lines.append("This report has no sections.")
    return "\n".join(lines)


def _render_workflow(workflow: Workflow) -> str:
    definition = workflow.definition
    lines = [
        f"Workflow: {definition.name}", f"Status: {workflow.status.value}",
        definition.description or "No description.",
    ]
    if definition.tags:
        lines.append(f"Tags: {', '.join(definition.tags)}")
    if definition.steps:
        lines.append("Steps:")
        lines.extend(
            f"- {index}. {step.name} (node: {step.node_name})" for index, step in enumerate(definition.steps, start=1)
        )
    else:
        lines.append("This workflow has no steps.")
    return "\n".join(lines)


def _render_reflection(reflection: ReflectionResult) -> str:
    review = reflection.review
    lines = [
        f"Outcome: {'successful' if review.overall_success else 'not fully successful'}.",
        f"Execution score: {review.execution_score.value:.0f}/100 ({review.execution_score.label}).",
        f"Efficiency score: {review.efficiency_score.value:.0f}/100 ({review.efficiency_score.label}).",
        f"Confidence score: {review.confidence_score.value:.0f}/100 ({review.confidence_score.label}).",
    ]
    if review.strengths:
        lines.append("Strengths:")
        lines.extend(f"- {strength}" for strength in review.strengths)
    if review.weaknesses:
        lines.append("Weaknesses:")
        lines.extend(f"- {weakness}" for weakness in review.weaknesses)
    if review.recommendations:
        lines.append("Recommendations:")
        lines.extend(f"- {rec.message}" for rec in review.recommendations[:_MAX_RECOMMENDATIONS])
    return "\n".join(lines)


def _render_optimization(optimization: OptimizationResult) -> str:
    lines = [f"Goal: {optimization.original_plan.goal or 'Not stated.'}"]
    if optimization.decisions:
        lines.append("Optimization decisions:")
        lines.extend(
            f"- [{decision.category.value}{' - applied' if decision.applied else ' - advisory'}] "
            f"{decision.message} ({decision.reason}, {decision.evidence_count} evidence point(s))"
            for decision in optimization.decisions[:_MAX_DECISIONS]
        )
    else:
        lines.append("No optimization decisions were suggested for this plan.")
    return "\n".join(lines)
