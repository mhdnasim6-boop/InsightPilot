"""GenerateExecutiveSummaryTool: wraps the prompt-build -> AIService.generate() -> parse
chain — moved verbatim from ExecutiveSummaryAgent's own former ``_build_prompt()``/
``_parse_draft()`` methods. The one existing *service* this tool calls is
``AIService.generate()``; prompt template registration/rendering and response
parsing are the same "thin translation" every other tool also owns (e.g.
QueryDatabaseTool's table-vs-query branch) — not new business logic.
"""

from pydantic import ValidationError

from backend.agents.browser.models.result import BrowserAgentResult
from backend.agents.executive_summary.models.draft import ExecutiveSummaryDraft
from backend.agents.executive_summary.prompts.templates import (
    PROMPT_NAME,
    WORKED_EXAMPLE_JSON,
    register_executive_summary_prompts,
)
from backend.agents.planner.parser.json_extractor import extract_json_object
from backend.ai.models.requests import AIRequest
from backend.ai.prompts.manager import PromptManager
from backend.reporting.exporters.markdown_exporter import MarkdownReportExporter
from backend.reporting.models.report_document import ReportDocument
from backend.services.ai_service import AIService
from backend.tools.base.tool import Tool
from backend.tools.models.inputs import GenerateExecutiveSummaryInput

_NO_EXTERNAL_CONTEXT_TEXT = "No external market context was available."


class GenerateExecutiveSummaryTool(Tool[GenerateExecutiveSummaryInput, ExecutiveSummaryDraft]):
    """Writes a grounded executive summary from a ReportDocument via exactly one AIService.generate() call."""

    name = "generate_executive_summary"
    description = (
        "Write a grounded executive summary (findings/risks/recommendations/next actions) "
        "from an already-built ReportDocument, via exactly one AI call."
    )
    input_model = GenerateExecutiveSummaryInput
    output_model = ExecutiveSummaryDraft

    def __init__(
        self,
        ai_service: AIService,
        prompt_manager: PromptManager,
        markdown_exporter: MarkdownReportExporter | None = None,
    ) -> None:
        self._ai_service = ai_service
        self._prompt_manager = prompt_manager
        self._markdown_exporter = markdown_exporter or MarkdownReportExporter()
        register_executive_summary_prompts(self._prompt_manager)

    async def execute(self, tool_input: GenerateExecutiveSummaryInput) -> ExecutiveSummaryDraft:
        prompt = self._build_prompt(tool_input.report_document, tool_input.browser_result)
        response = await self._ai_service.generate(AIRequest(prompt=prompt))
        return self._parse_draft(response.content)

    def _build_prompt(self, report_document: ReportDocument, browser_result: BrowserAgentResult | None) -> str:
        return self._prompt_manager.get(
            PROMPT_NAME,
            worked_example_json=WORKED_EXAMPLE_JSON,
            report_content=self._markdown_exporter.export(report_document),
            external_context=_render_external_context(browser_result),
        )

    def _parse_draft(self, content: str) -> ExecutiveSummaryDraft:
        """Extract and validate an ``ExecutiveSummaryDraft`` from raw AI-response text.

        Raises ``ValueError``/``pydantic.ValidationError`` if no JSON
        object is found or it doesn't match the expected schema — both
        caught generically by the calling agent's own try/except,
        exactly as before this phase.
        """
        raw_json = extract_json_object(content)
        try:
            return ExecutiveSummaryDraft.model_validate_json(raw_json)
        except ValidationError as exc:
            raise ValueError(f"AI response did not match the expected executive summary schema: {exc}") from exc


def _render_external_context(browser_result: BrowserAgentResult | None) -> str:
    """A safe, plain-text view of BrowserAgentResult's own summaries — nothing recomputed."""
    if browser_result is None or not browser_result.summaries:
        return _NO_EXTERNAL_CONTEXT_TEXT
    return "\n".join(f"- {summary.query}: {summary.summary}" for summary in browser_result.summaries)
