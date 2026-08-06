"""Structural validation for a generated ``ReportDocument``.

Checks four things: section order is unique, the sections its template
declared required are present, and every chart/KPI a section references
actually existed in the source ``VisualizationResult``/``AnalysisResult``
— a defensive check against a builder bug producing a dangling reference,
not something a well-behaved ``ReportBuilder`` run should ever trigger.
"""

from backend.analysis.models.result import AnalysisResult
from backend.ingestion.validators.result import IssueSeverity, ValidationIssue
from backend.reporting.models.report_document import ReportDocument
from backend.reporting.sections.content_blocks import KPIGridBlock
from backend.reporting.sections.section import ReportSection
from backend.reporting.templates.report_template import ReportTemplateType, get_template
from backend.reporting.validation.result import ReportValidationResult
from backend.visualization.models.result import VisualizationResult


class ReportValidator:
    """Validates a ``ReportDocument``'s structure against its declared template and sources."""

    def validate(
        self,
        document: ReportDocument,
        analysis_result: AnalysisResult | None = None,
        visualization_result: VisualizationResult | None = None,
    ) -> ReportValidationResult:
        """Validate ``document``. Chart/KPI reference checks only run when the source is given."""
        issues: list[ValidationIssue] = [
            *self._check_has_sections(document),
            *self._check_unique_order(document),
            *self._check_required_sections(document),
            *self._check_chart_references(document, visualization_result),
            *self._check_kpi_references(document, analysis_result),
        ]
        is_valid = not any(issue.severity == IssueSeverity.ERROR for issue in issues)
        return ReportValidationResult(is_valid=is_valid, issues=issues)

    def _check_has_sections(self, document: ReportDocument) -> list[ValidationIssue]:
        if not document.sections:
            return [ValidationIssue(severity=IssueSeverity.ERROR, code="no_sections", message="Report has no sections.")]
        return []

    def _check_unique_order(self, document: ReportDocument) -> list[ValidationIssue]:
        orders = [section.order for section in document.sections]
        duplicates = sorted({order for order in orders if orders.count(order) > 1})
        if duplicates:
            return [
                ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="duplicate_section_order",
                    message=f"Section order values are not unique: {duplicates}.",
                )
            ]
        return []

    def _check_required_sections(self, document: ReportDocument) -> list[ValidationIssue]:
        template_type_value = document.metadata.get("template_type")
        if not template_type_value:
            return []
        try:
            template = get_template(ReportTemplateType(template_type_value))
        except ValueError:
            return [
                ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    code="unknown_template_type",
                    message=f"Unrecognized template_type in metadata: '{template_type_value}'.",
                )
            ]
        present_ids = {section.section_id for section in document.sections}
        return [
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="missing_required_section",
                message=f"Required section '{kind.value}' is missing.",
            )
            for kind in template.required_sections
            if kind.value not in present_ids
        ]

    def _check_chart_references(
        self, document: ReportDocument, visualization_result: VisualizationResult | None
    ) -> list[ValidationIssue]:
        if visualization_result is None:
            return []
        known_chart_ids = {chart.chart_id for chart in visualization_result.charts}
        return [
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="unknown_chart_reference",
                message=f"Section '{section.section_id}' references unknown chart_id '{chart_id}'.",
            )
            for section in self._all_sections(document)
            for chart_id in section.charts
            if chart_id not in known_chart_ids
        ]

    def _check_kpi_references(
        self, document: ReportDocument, analysis_result: AnalysisResult | None
    ) -> list[ValidationIssue]:
        if analysis_result is None:
            return []
        known_kpi_names = {kpi.name for kpi in analysis_result.kpis}
        issues: list[ValidationIssue] = []
        for section in self._all_sections(document):
            for block in section.content_blocks:
                if not isinstance(block, KPIGridBlock):
                    continue
                issues.extend(
                    ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="unknown_kpi_reference",
                        message=f"Section '{section.section_id}' references unknown KPI '{entry.name}'.",
                    )
                    for entry in block.kpis
                    if entry.name not in known_kpi_names
                )
        return issues

    def _all_sections(self, document: ReportDocument) -> list[ReportSection]:
        return [*document.sections, *document.appendices]
