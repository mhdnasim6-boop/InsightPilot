"""Input models for every tool.

Each mirrors exactly the parameters the agent currently passes to the
one service call it wraps — no field an agent doesn't already use today.
Outputs are never redefined here: every tool returns an existing domain
model directly (``BusinessDataset``, ``CleaningOutcome``,
``AnalysisResult``, ``VisualizationResult``, ``ReportDocument``,
``SearchOutcome``, ``ExecutiveSummaryDraft``) — the same "reuse the
domain model" pattern every prior phase has followed.
"""

from pydantic import BaseModel

from backend.agents.browser.models.result import BrowserAgentResult
from backend.analysis.models.result import AnalysisResult
from backend.cleaning.models.outcome import CleaningOutcome
from backend.datasource.sql.models.connection_config import SQLConnectionConfig
from backend.ingestion.models.dataset import BusinessDataset
from backend.reporting.models.report_document import ReportDocument
from backend.reporting.templates.report_template import ReportTemplateType
from backend.visualization.models.result import VisualizationResult


class IngestDatasetInput(BaseModel):
    """Input for IngestDatasetTool — wraps ``IngestionService.ingest()``."""

    dataset_reference: str


class CleanDatasetInput(BaseModel):
    """Input for CleanDatasetTool — wraps ``CleaningService.clean()``."""

    dataset: BusinessDataset


class AnalyzeDatasetInput(BaseModel):
    """Input for AnalyzeDatasetTool — wraps ``AnalysisService.analyze()``."""

    cleaning_outcome: CleaningOutcome


class GenerateVisualizationInput(BaseModel):
    """Input for GenerateVisualizationTool — wraps ``VisualizationService.generate()``."""

    analysis_result: AnalysisResult
    dataset: BusinessDataset | None = None


class GenerateReportInput(BaseModel):
    """Input for GenerateReportTool — wraps ``ReportService.build_report()``."""

    dataset: BusinessDataset
    cleaning_outcome: CleaningOutcome | None = None
    analysis_result: AnalysisResult | None = None
    visualization_result: VisualizationResult | None = None
    template_type: ReportTemplateType = ReportTemplateType.BUSINESS_REPORT
    theme: str = "corporate"
    title: str | None = None
    subtitle: str | None = None
    author: str | None = None


class QueryDatabaseInput(BaseModel):
    """Input for QueryDatabaseTool — wraps ``SQLDataSourceService.import_table()``/``.import_query()``.

    Exactly one of ``table_name``/``query`` is expected — mirroring
    SQLAgent's own existing exactly-one-of contract, still enforced by
    SQLAgent's ``validate_agent_input`` before this tool is ever called,
    not duplicated here.
    """

    connection: SQLConnectionConfig
    table_name: str | None = None
    query: str | None = None
    dataset_name: str | None = None


class SearchWebInput(BaseModel):
    """Input for SearchWebTool — wraps ``BrowserService.search()``. One query per call."""

    query: str


class GenerateExecutiveSummaryInput(BaseModel):
    """Input for GenerateExecutiveSummaryTool — wraps the prompt-build -> AIService.generate() -> parse chain."""

    report_document: ReportDocument
    browser_result: BrowserAgentResult | None = None
