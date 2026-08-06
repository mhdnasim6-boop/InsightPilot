"""ReportBuilder: turns already-computed pipeline outputs into a ReportDocument.

Never computes a statistic, never recommends a chart, never touches a
DataFrame — it only reads facts ``AnalysisService``/``VisualizationService``/
``CleaningService``/``PlannerService`` already produced and arranges them
into sections. Every optional input that's missing simply means the
sections that would have needed it are omitted — never fabricated.
"""

from typing import Any

from pydantic import BaseModel

from backend.agents.planner.models.io import PlannerOutput
from backend.analysis.models.result import AnalysisResult
from backend.cleaning.models.outcome import CleaningOutcome
from backend.ingestion.models.dataset import BusinessDataset
from backend.reporting.models.report_document import (
    ReportDocument,
    TableOfContentsEntry,
)
from backend.reporting.sections.content_blocks import (
    BulletListBlock,
    ChartReferenceBlock,
    KPIGridBlock,
    ParagraphBlock,
    ReportKPIEntry,
    TableBlock,
)
from backend.reporting.sections.section import ReportSection, ReportSectionKind
from backend.reporting.templates.report_template import ReportTemplateType, get_template
from backend.utils.ids import generate_id
from backend.utils.time import utc_now
from backend.visualization.models.result import VisualizationResult

_MAX_APPENDIX_SAMPLE_ROWS = 20


class _ReportInputs(BaseModel):
    """Bundles one build's inputs so section builders don't each take five parameters."""

    model_config = {"arbitrary_types_allowed": True}

    dataset: BusinessDataset
    cleaning_outcome: CleaningOutcome | None = None
    analysis_result: AnalysisResult | None = None
    visualization_result: VisualizationResult | None = None
    planner_output: PlannerOutput | None = None


class ReportBuilder:
    """Builds a ``ReportDocument`` from a dataset and whatever pipeline outputs are available."""

    def build(
        self,
        dataset: BusinessDataset,
        cleaning_outcome: CleaningOutcome | None = None,
        analysis_result: AnalysisResult | None = None,
        visualization_result: VisualizationResult | None = None,
        planner_output: PlannerOutput | None = None,
        template_type: ReportTemplateType = ReportTemplateType.BUSINESS_REPORT,
        theme: str = "corporate",
        title: str | None = None,
        subtitle: str | None = None,
        author: str | None = None,
    ) -> ReportDocument:
        """Build a ``ReportDocument`` using ``template_type`` to decide which sections to include."""
        template = get_template(template_type)
        inputs = _ReportInputs(
            dataset=dataset,
            cleaning_outcome=cleaning_outcome,
            analysis_result=analysis_result,
            visualization_result=visualization_result,
            planner_output=planner_output,
        )

        sections: list[ReportSection] = []
        for kind in template.section_order:
            section = self._build_section(kind, inputs, order=len(sections))
            if section is not None:
                sections.append(section)

        appendices: list[ReportSection] = []
        if template.include_appendix:
            appendix = self._build_appendix(inputs, order=0)
            if appendix is not None:
                appendices.append(appendix)

        toc = [TableOfContentsEntry(section_id=s.section_id, title=s.title, order=s.order) for s in sections]
        toc.extend(
            TableOfContentsEntry(section_id=a.section_id, title=a.title, order=len(sections) + i)
            for i, a in enumerate(appendices)
        )

        return ReportDocument(
            report_id=generate_id(),
            title=title or f"{dataset.dataset_name} Report",
            subtitle=subtitle,
            generated_at=utc_now(),
            author=author,
            theme=theme,
            table_of_contents=toc,
            sections=sections,
            appendices=appendices,
            metadata={"template_type": template_type.value, "dataset_id": dataset.dataset_id},
        )

    # -- Section dispatch -------------------------------------------------------

    def _build_section(self, kind: ReportSectionKind, inputs: _ReportInputs, order: int) -> ReportSection | None:
        builders = {
            ReportSectionKind.OVERVIEW: self._build_overview,
            ReportSectionKind.DATASET_SUMMARY: self._build_dataset_summary,
            ReportSectionKind.CLEANING_SUMMARY: self._build_cleaning_summary,
            ReportSectionKind.ANALYSIS: self._build_analysis,
            ReportSectionKind.KPIS: self._build_kpis,
            ReportSectionKind.CHARTS: self._build_charts,
            ReportSectionKind.INSIGHTS: self._build_insights,
        }
        return builders[kind](inputs, order)

    # -- Individual sections ------------------------------------------------------

    def _build_overview(self, inputs: _ReportInputs, order: int) -> ReportSection:
        dataset = inputs.dataset
        blocks: list[Any] = [
            ParagraphBlock(
                text=(
                    f"This report covers the dataset '{dataset.dataset_name}' "
                    f"({dataset.row_count} rows, {dataset.column_count} columns), generated on "
                    f"{utc_now().strftime('%Y-%m-%d')}."
                )
            )
        ]
        if inputs.planner_output is not None:
            blocks.append(ParagraphBlock(text=inputs.planner_output.goal))

        facts = [
            f"Source type: {dataset.source_type.value}",
            f"Rows: {dataset.row_count}, Columns: {dataset.column_count}",
        ]
        if inputs.cleaning_outcome is not None:
            facts.append(f"Data quality score: {inputs.cleaning_outcome.result.quality_score}")
        if inputs.analysis_result is not None:
            facts.append(f"KPIs computed: {len(inputs.analysis_result.kpis)}")
        if inputs.visualization_result is not None:
            facts.append(f"Charts generated: {len(inputs.visualization_result.charts)}")
        blocks.append(BulletListBlock(items=facts))

        return ReportSection(
            section_id=ReportSectionKind.OVERVIEW.value, title="Overview", order=order, content_blocks=blocks
        )

    def _build_dataset_summary(self, inputs: _ReportInputs, order: int) -> ReportSection:
        dataset = inputs.dataset
        blocks: list[Any] = [
            ParagraphBlock(
                text=(
                    f"The dataset has {dataset.row_count} rows and {dataset.column_count} columns, "
                    f"sourced from {dataset.source_type.value}."
                )
            ),
            TableBlock(
                headers=["Column", "Type", "Non-Null", "Null", "Unique"],
                rows=[
                    [column.name, column.dtype, column.non_null_count, column.null_count, column.unique_count]
                    for column in dataset.columns
                ],
                caption="Column metadata",
            ),
        ]
        return ReportSection(
            section_id=ReportSectionKind.DATASET_SUMMARY.value,
            title="Dataset Summary",
            order=order,
            content_blocks=blocks,
            tables=["Column metadata"],
        )

    def _build_cleaning_summary(self, inputs: _ReportInputs, order: int) -> ReportSection | None:
        if inputs.cleaning_outcome is None:
            return None
        result = inputs.cleaning_outcome.result
        blocks: list[Any] = [
            ParagraphBlock(text=f"{result.summary} Quality score: {result.quality_score}."),
            TableBlock(
                headers=["Rule", "Rows Before", "Rows After", "Columns Affected"],
                rows=[
                    [step.rule_name, step.rows_before, step.rows_after, ", ".join(step.columns_affected)]
                    for step in result.steps_applied
                ],
                caption="Cleaning steps applied",
            ),
        ]
        if result.warnings:
            blocks.append(BulletListBlock(items=result.warnings))
        return ReportSection(
            section_id=ReportSectionKind.CLEANING_SUMMARY.value,
            title="Cleaning Summary",
            order=order,
            content_blocks=blocks,
            tables=["Cleaning steps applied"],
        )

    def _build_analysis(self, inputs: _ReportInputs, order: int) -> ReportSection | None:
        if inputs.analysis_result is None:
            return None
        result = inputs.analysis_result
        summary = result.dataset_summary
        blocks: list[Any] = [
            ParagraphBlock(
                text=(
                    f"{len(summary.numeric_columns)} numeric column(s), "
                    f"{len(summary.categorical_columns)} categorical column(s), "
                    f"{summary.missing_values} missing value(s) across the dataset."
                )
            )
        ]
        if result.descriptive_statistics.columns:
            blocks.append(
                TableBlock(
                    headers=["Column", "Mean", "Median", "Std Dev", "Min", "Max"],
                    rows=[
                        [name, stats.mean, stats.median, stats.std, stats.minimum, stats.maximum]
                        for name, stats in result.descriptive_statistics.columns.items()
                    ],
                    caption="Descriptive statistics",
                )
            )

        blocks.append(ParagraphBlock(text=self._describe_trends(result)))
        blocks.append(ParagraphBlock(text=self._describe_correlations(result)))
        blocks.append(ParagraphBlock(text=self._describe_anomalies(result)))

        return ReportSection(
            section_id=ReportSectionKind.ANALYSIS.value,
            title="Analysis",
            order=order,
            content_blocks=blocks,
            tables=["Descriptive statistics"] if result.descriptive_statistics.columns else [],
        )

    def _build_kpis(self, inputs: _ReportInputs, order: int) -> ReportSection | None:
        if inputs.analysis_result is None or not inputs.analysis_result.kpis:
            return None
        kpis = [
            ReportKPIEntry(name=kpi.name, value=kpi.value, kpi_type=kpi.kpi_type.value)
            for kpi in inputs.analysis_result.kpis
        ]
        return ReportSection(
            section_id=ReportSectionKind.KPIS.value,
            title="KPIs",
            order=order,
            content_blocks=[KPIGridBlock(kpis=kpis)],
        )

    def _build_charts(self, inputs: _ReportInputs, order: int) -> ReportSection | None:
        if inputs.visualization_result is None or not inputs.visualization_result.charts:
            return None
        charts = sorted(inputs.visualization_result.charts, key=lambda chart: chart.priority, reverse=True)
        blocks: list[Any] = [
            ChartReferenceBlock(
                chart_id=chart.chart_id,
                title=chart.title,
                chart_type=chart.chart_type.value,
                caption=chart.description,
            )
            for chart in charts
        ]
        if inputs.visualization_result.recommendations:
            blocks.append(BulletListBlock(items=inputs.visualization_result.recommendations))
        return ReportSection(
            section_id=ReportSectionKind.CHARTS.value,
            title="Charts",
            order=order,
            content_blocks=blocks,
            charts=[chart.chart_id for chart in charts],
        )

    def _build_insights(self, inputs: _ReportInputs, order: int) -> ReportSection | None:
        if inputs.analysis_result is None or not inputs.analysis_result.insights:
            return None
        items = [insight.message for insight in inputs.analysis_result.insights]
        return ReportSection(
            section_id=ReportSectionKind.INSIGHTS.value,
            title="Insights",
            order=order,
            content_blocks=[BulletListBlock(items=items)],
        )

    def _build_appendix(self, inputs: _ReportInputs, order: int) -> ReportSection | None:
        """Supplementary detail not already shown in the main body — never a duplicate of it."""
        blocks: list[Any] = []
        tables: list[str] = []

        if inputs.dataset.sample_rows:
            sample = inputs.dataset.sample_rows[:_MAX_APPENDIX_SAMPLE_ROWS]
            headers = list(sample[0].keys())
            blocks.append(
                TableBlock(
                    headers=headers,
                    rows=[[row.get(header) for header in headers] for row in sample],
                    caption="Sample rows",
                )
            )
            tables.append("Sample rows")

        if inputs.analysis_result is not None and inputs.analysis_result.correlations.applicable:
            matrix = inputs.analysis_result.correlations.pearson_matrix
            if matrix:
                columns = inputs.analysis_result.correlations.columns
                blocks.append(
                    TableBlock(
                        headers=["Column", *columns],
                        rows=[[column, *(matrix.get(column, {}).get(other) for other in columns)] for column in columns],
                        caption="Full Pearson correlation matrix",
                    )
                )
                tables.append("Full Pearson correlation matrix")

        if inputs.planner_output is not None and inputs.planner_output.execution_plan.steps:
            blocks.append(
                TableBlock(
                    headers=["Step", "Node", "Status"],
                    rows=[
                        [step.name, step.node_name, step.status.value]
                        for step in inputs.planner_output.execution_plan.steps
                    ],
                    caption="Execution plan steps",
                )
            )
            tables.append("Execution plan steps")

        warnings = [*(inputs.analysis_result.warnings if inputs.analysis_result else [])]
        warnings += inputs.visualization_result.warnings if inputs.visualization_result else []
        if warnings:
            blocks.append(BulletListBlock(items=warnings))

        if not blocks:
            return None

        return ReportSection(
            section_id=ReportSectionKind.APPENDIX.value,
            title="Appendix",
            order=order,
            content_blocks=blocks,
            tables=tables,
        )

    # -- Pure text helpers --------------------------------------------------------

    def _describe_trends(self, result: AnalysisResult) -> str:
        trends = result.trends
        if not trends.applicable:
            return f"Trend analysis: not applicable. {trends.reason or ''}".strip()
        series_summary = "; ".join(
            f"{series.column} (growth rate: {series.growth_rate})" for series in trends.series
        )
        return f"Trend analysis (time column: {trends.time_column}): {series_summary or 'no series computed'}."

    def _describe_correlations(self, result: AnalysisResult) -> str:
        correlations = result.correlations
        if not correlations.applicable:
            return f"Correlation analysis: not applicable. {correlations.reason or ''}".strip()
        strong = len(correlations.strong_positive) + len(correlations.strong_negative)
        return f"Correlation analysis found {strong} strong relationship(s) among {len(correlations.columns)} numeric column(s)."

    def _describe_anomalies(self, result: AnalysisResult) -> str:
        anomalies = result.anomalies
        if not anomalies.applicable:
            return f"Anomaly detection: not applicable. {anomalies.reason or ''}".strip()
        total_outliers = sum(column.zscore_outlier_count for column in anomalies.columns)
        return f"Anomaly detection found {total_outliers} Z-score outlier(s) across {len(anomalies.columns)} column(s)."
