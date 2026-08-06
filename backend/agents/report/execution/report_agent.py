"""ReportAgent: orchestrates GenerateReportTool for one ExecutionStep.

One ``GenerateReportTool.execute()`` call (Tool Layer, Phase 22) — never
a ``ReportBuilder``, ``ReportValidator``, ``ReportStore``, or exporter
directly, and no statistics/charts/analysis of its own; all of that
lives behind ``ReportService``, which ``GenerateReportTool`` wraps. A
downstream failure (e.g. ``ReportValidationFailedError``) degrades to a
FAILED ``ReportAgentResult`` rather than a crash — only malformed
*input* (see ``validate_agent_input``) raises immediately. A given
``BrowserAgentResult`` is never passed into report *construction*
(``GenerateReportTool``/``ReportService`` have no such parameter, and
this phase adds no new reporting logic) — it is summarized into
``ReportAgentResult.metadata["external_context"]`` instead, so a report
is byte-identical whether or not BrowserAgent ran, and the canonical
``ReportDocument`` stored in ``ReportStore`` never depends on external,
unverified context.
"""

import time

from loguru import logger

from backend.agents.browser.models.result import BrowserAgentResult
from backend.agents.report.models.result import ReportAgentResult
from backend.agents.report.validation.input_validator import validate_agent_input
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep
from backend.tools.execution.generate_report_tool import GenerateReportTool
from backend.tools.models.inputs import GenerateReportInput


class ReportAgent:
    """Runs GenerateReportTool for one step, and nothing else."""

    def __init__(self, generate_report_tool: GenerateReportTool) -> None:
        self._generate_report_tool = generate_report_tool

    async def execute(self, step: ExecutionStep, session_id: str | None) -> ReportAgentResult:
        """Build a report for ``step`` and return the outcome.

        Raises ``InvalidAgentInputError`` for malformed input (missing
        session/dataset, a present field with the wrong shape, or an
        unrecognized ``report_config.template_type``). A report-building
        failure is captured in the returned result's ``status``/
        ``warnings`` instead of raising.
        """
        dataset, cleaning_outcome, analysis_result, visualization_result, browser_result, template_type, config = (
            validate_agent_input(step, session_id)
        )
        theme = config.get("theme") or "corporate"

        start = time.perf_counter()
        warnings: list[str] = []
        document = None
        status = ExecutionStatus.COMPLETED

        try:
            document = await self._generate_report_tool.execute(
                GenerateReportInput(
                    dataset=dataset,
                    cleaning_outcome=cleaning_outcome,
                    analysis_result=analysis_result,
                    visualization_result=visualization_result,
                    template_type=template_type,
                    theme=str(theme),
                    title=_optional_str(config.get("title")),
                    subtitle=_optional_str(config.get("subtitle")),
                    author=_optional_str(config.get("author")),
                )
            )
        except Exception as exc:  # noqa: BLE001 - a report-building failure degrades to a FAILED result, not a crash
            logger.exception("ReportAgent step '{}' failed", step.step_id)
            warnings.append(str(exc))
            status = ExecutionStatus.FAILED

        execution_time = time.perf_counter() - start
        return ReportAgentResult(
            step_id=step.step_id,
            status=status,
            report_id=document.report_id if document is not None else None,
            report_document=document,
            warnings=warnings,
            execution_time=execution_time,
            metadata={
                "session_id": session_id,
                "dataset_id": dataset.dataset_id,
                "template_type": template_type.value,
                "theme": theme,
                "external_context": _summarize_browser_context(browser_result),
            },
        )


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _summarize_browser_context(browser_result: BrowserAgentResult | None) -> dict[str, object] | None:
    """A safe, small view of BrowserAgentResult for ReportAgentResult.metadata — never the report itself."""
    if browser_result is None:
        return None
    return {
        "queries": browser_result.metadata.get("queries", []),
        "source_count": len(browser_result.sources),
        "summaries": [{"query": summary.query, "summary": summary.summary} for summary in browser_result.summaries],
    }
