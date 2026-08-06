"""GenerateReportTool: wraps ReportService.build_report() — nothing else.

Shared by FileAgent, SQLAgent, and ReportAgent — the same tool instance
type backs all three, since all three currently make the exact same
``ReportService.build_report()`` call.
"""

from backend.reporting.models.report_document import ReportDocument
from backend.services.report_service import ReportService
from backend.tools.base.tool import Tool
from backend.tools.models.inputs import GenerateReportInput


class GenerateReportTool(Tool[GenerateReportInput, ReportDocument]):
    """Builds, validates, and stores a new ReportDocument."""

    name = "generate_report"
    description = "Build, validate, and store a ReportDocument from a dataset and its pipeline outputs."
    input_model = GenerateReportInput
    output_model = ReportDocument

    def __init__(self, report_service: ReportService) -> None:
        self._report_service = report_service

    async def execute(self, tool_input: GenerateReportInput) -> ReportDocument:
        return self._report_service.build_report(
            tool_input.dataset,
            cleaning_outcome=tool_input.cleaning_outcome,
            analysis_result=tool_input.analysis_result,
            visualization_result=tool_input.visualization_result,
            template_type=tool_input.template_type,
            theme=tool_input.theme,
            title=tool_input.title,
            subtitle=tool_input.subtitle,
            author=tool_input.author,
        )
