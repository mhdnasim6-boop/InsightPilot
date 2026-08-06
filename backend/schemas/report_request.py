"""Request body for POST /api/v1/reports."""

from pydantic import BaseModel

from backend.agents.planner.models.io import PlannerOutput
from backend.analysis.models.result import AnalysisResult
from backend.cleaning.models.outcome import CleaningOutcome
from backend.ingestion.models.dataset import BusinessDataset
from backend.reporting.templates.report_template import ReportTemplateType
from backend.visualization.models.result import VisualizationResult


class ReportGenerateRequest(BaseModel):
    """Everything needed to build a ReportDocument over HTTP.

    Only ``dataset`` is required — the pipeline outputs the frontend
    already holds in session state (cleaning/analysis/visualization/planner)
    are passed straight back; any that are omitted simply mean the
    sections that would have needed them are left out of the report.
    """

    dataset: BusinessDataset
    cleaning_outcome: CleaningOutcome | None = None
    analysis_result: AnalysisResult | None = None
    visualization_result: VisualizationResult | None = None
    planner_output: PlannerOutput | None = None
    template_type: ReportTemplateType = ReportTemplateType.BUSINESS_REPORT
    theme: str = "corporate"
    title: str | None = None
    subtitle: str | None = None
    author: str | None = None
