"""ExecutiveSummaryAgent: turns an already-built ReportDocument into a concise,
grounded executive summary via GenerateExecutiveSummaryTool.

Never calls AnalysisService, VisualizationService, ReportBuilder,
CleaningService, a SQL service, or BrowserService — the only work this
class delegates to at all is the single
``GenerateExecutiveSummaryTool.execute()`` call in ``execute()`` (Tool
Layer, Phase 22), which itself makes exactly one ``AIService.generate()``
call internally. Grounding is enforced structurally, not just by prompt
instruction: the model only ever sees text rendered from the given
``ReportDocument`` and, optionally, an already-computed
``BrowserAgentResult``'s own summaries — both handled inside the tool,
unchanged from before this phase. A malformed or unparseable model
response degrades to a FAILED result, never a crash — only malformed
*input* (see ``validate_agent_input``) raises immediately.
"""

import time

from loguru import logger

from backend.agents.executive_summary.models.draft import ExecutiveSummaryDraft
from backend.agents.executive_summary.models.result import ExecutiveSummaryResult
from backend.agents.executive_summary.validation.input_validator import (
    validate_agent_input,
)
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep
from backend.tools.execution.generate_executive_summary_tool import (
    GenerateExecutiveSummaryTool,
)
from backend.tools.models.inputs import GenerateExecutiveSummaryInput


class ExecutiveSummaryAgent:
    """Reads a ReportDocument (+ optional external context) and writes an executive summary, via a tool."""

    def __init__(self, generate_executive_summary_tool: GenerateExecutiveSummaryTool) -> None:
        self._generate_executive_summary_tool = generate_executive_summary_tool

    async def execute(self, step: ExecutionStep, session_id: str | None) -> ExecutiveSummaryResult:
        """Write an executive summary for ``step`` and return the outcome.

        Raises ``InvalidAgentInputError`` for malformed input (missing
        session/report_document, or a present field with the wrong
        shape). A malformed AI response, or the AI call itself failing,
        is captured in the returned result's ``status``/``warnings``
        instead of raising.
        """
        report_document, browser_result, dataset_metadata, analysis_metadata = validate_agent_input(
            step, session_id
        )

        start = time.perf_counter()
        warnings: list[str] = []
        draft: ExecutiveSummaryDraft | None = None
        status = ExecutionStatus.COMPLETED

        try:
            draft = await self._generate_executive_summary_tool.execute(
                GenerateExecutiveSummaryInput(report_document=report_document, browser_result=browser_result)
            )
        except Exception as exc:  # noqa: BLE001 - a bad AI call/response degrades to a FAILED result, not a crash
            logger.exception("ExecutiveSummaryAgent step '{}' failed", step.step_id)
            warnings.append(str(exc))
            status = ExecutionStatus.FAILED

        execution_time = time.perf_counter() - start
        return ExecutiveSummaryResult(
            step_id=step.step_id,
            status=status,
            executive_summary=draft.executive_summary if draft else "",
            key_findings=draft.key_findings if draft else [],
            risks=draft.risks if draft else [],
            recommendations=draft.recommendations if draft else [],
            follow_up_actions=draft.follow_up_actions if draft else [],
            confidence=draft.confidence if draft else 0.0,
            warnings=warnings,
            execution_time=execution_time,
            metadata={
                "session_id": session_id,
                "report_id": report_document.report_id,
                "external_context_included": browser_result is not None,
                "dataset_metadata": dataset_metadata,
                "analysis_metadata": analysis_metadata,
            },
        )
