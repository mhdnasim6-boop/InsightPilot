"""Report generation entry point.

The only object anything (a router, a test) should use to build,
validate, or export a report — never ``ReportBuilder``, ``ReportValidator``,
the ``ReportStore``, or an exporter directly.

``memory_service`` is an optional collaborator: every report built here
is remembered as a REPORT ``MemoryItem`` — the single place this
happens regardless of whether a File/SQL/Report agent or the direct
``/reports`` endpoint triggered the build (``GenerateReportTool`` — used
by all three agents — calls ``build_report()`` directly), so this one
hook covers every report-creation path with no duplicated logic.
"""

from collections.abc import Callable

from backend.agents.planner.models.io import PlannerOutput
from backend.analysis.models.result import AnalysisResult
from backend.cleaning.models.outcome import CleaningOutcome
from backend.ingestion.models.dataset import BusinessDataset
from backend.memory.models.memory_reference import MemoryReference
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.reporting.builders.report_builder import ReportBuilder
from backend.reporting.exceptions.errors import (
    ReportNotFoundError,
    ReportValidationFailedError,
)
from backend.reporting.exporters.json_exporter import JSONReportExporter
from backend.reporting.exporters.markdown_exporter import MarkdownReportExporter
from backend.reporting.exporters.placeholders import (
    PDFReportExporter,
    PowerPointReportExporter,
    WordReportExporter,
)
from backend.reporting.models.report_document import ReportDocument, ReportExportFormat
from backend.reporting.report_store import ReportStore
from backend.reporting.templates.report_template import ReportTemplateType
from backend.reporting.validation.result import ReportValidationResult
from backend.reporting.validation.validator import ReportValidator
from backend.visualization.models.placeholder import ExportPlaceholder
from backend.visualization.models.result import VisualizationResult

_ExporterFn = Callable[[ReportDocument], "str | ExportPlaceholder"]


class ReportService:
    """Builds, validates, stores, and exports ``ReportDocument``s."""

    def __init__(
        self,
        builder: ReportBuilder,
        validator: ReportValidator,
        report_store: ReportStore,
        json_exporter: JSONReportExporter | None = None,
        markdown_exporter: MarkdownReportExporter | None = None,
        pdf_exporter: PDFReportExporter | None = None,
        word_exporter: WordReportExporter | None = None,
        powerpoint_exporter: PowerPointReportExporter | None = None,
        memory_service: MemoryService | None = None,
    ) -> None:
        self._builder = builder
        self._validator = validator
        self._report_store = report_store
        self._memory_service = memory_service
        self._exporters: dict[ReportExportFormat, _ExporterFn] = {
            ReportExportFormat.JSON: (json_exporter or JSONReportExporter()).export,
            ReportExportFormat.MARKDOWN: (markdown_exporter or MarkdownReportExporter()).export,
            ReportExportFormat.PDF: (pdf_exporter or PDFReportExporter()).export,
            ReportExportFormat.WORD: (word_exporter or WordReportExporter()).export,
            ReportExportFormat.POWERPOINT: (powerpoint_exporter or PowerPointReportExporter()).export,
        }

    def build_report(
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
        """Build, validate, and store a new ``ReportDocument``.

        Raises ``ReportValidationFailedError`` if the freshly-built
        document fails validation — a fail-fast guard against a
        ``ReportBuilder`` bug producing a dangling reference; a
        well-formed build should never trigger this.
        """
        document = self._builder.build(
            dataset,
            cleaning_outcome,
            analysis_result,
            visualization_result,
            planner_output,
            template_type,
            theme,
            title,
            subtitle,
            author,
        )
        result = self._validator.validate(document, analysis_result, visualization_result)
        if not result.is_valid:
            raise ReportValidationFailedError(
                f"Generated report '{document.report_id}' failed validation.", detail=result
            )

        self._report_store.put(document)
        self._remember_report(document)
        return document

    def _remember_report(self, document: ReportDocument) -> None:
        if self._memory_service is None:
            return
        self._memory_service.remember(
            title=f"Report: {document.title}",
            summary=document.subtitle or document.title,
            memory_type=MemoryType.REPORT,
            scope=MemoryScope.PROJECT,
            content={"report_id": document.report_id, "theme": document.theme, "version": document.version},
            tags=["report"],
            references=[MemoryReference(reference_type="report", reference_id=document.report_id)],
        )

    def get_report(self, report_id: str) -> ReportDocument:
        """Fetch a previously generated report. Raises ``ReportNotFoundError`` if unknown."""
        document = self._report_store.get(report_id)
        if document is None:
            raise ReportNotFoundError(f"Report '{report_id}' was not found.")
        return document

    def list_reports(self) -> list[ReportDocument]:
        """Return every report generated so far, most recently added first."""
        return self._report_store.list()

    def validate_report(
        self,
        document: ReportDocument,
        analysis_result: AnalysisResult | None = None,
        visualization_result: VisualizationResult | None = None,
    ) -> ReportValidationResult:
        """Validate any ``ReportDocument`` without raising — the caller decides what to do with it."""
        return self._validator.validate(document, analysis_result, visualization_result)

    def export_report(self, report_id: str, export_format: ReportExportFormat) -> "str | ExportPlaceholder":
        """Export a previously generated report.

        Every stored report already passed validation when it was built
        (``build_report`` never stores an invalid one), so this does not
        re-validate — it only fetches and exports.
        """
        document = self.get_report(report_id)
        return self._exporters[export_format](document)
