"""Validates ExecutiveSummaryAgent's own inputs before AIService is called.

``report_document`` is the only required input, mirroring ReportAgent's
own required ``dataset`` — it is ExecutiveSummaryAgent's primary (and
only strictly necessary) source of grounding. ``browser_agent_result``,
``dataset_metadata``, and ``analysis_metadata`` are all optional context
carried through to the prompt/result, never required.
"""

from pydantic import ValidationError

from backend.agents.browser.models.result import BrowserAgentResult
from backend.agents.file.exceptions.errors import InvalidAgentInputError
from backend.planning.models.step import ExecutionStep
from backend.reporting.models.report_document import ReportDocument


def validate_agent_input(
    step: ExecutionStep, session_id: str | None
) -> tuple[ReportDocument, BrowserAgentResult | None, dict[str, object], dict[str, object]]:
    """Check that ``step``/``session_id`` carry what ExecutiveSummaryAgent needs to run.

    Returns ``(report_document, browser_result, dataset_metadata,
    analysis_metadata)``. Raises ``InvalidAgentInputError`` if the
    session is missing, ``report_document`` is absent or malformed, or
    any present optional field is the wrong shape.
    """
    if not session_id or not session_id.strip():
        raise InvalidAgentInputError(f"ExecutiveSummaryAgent step '{step.step_id}' has no session_id.")

    raw_report = step.inputs.get("report_document")
    if not isinstance(raw_report, dict):
        raise InvalidAgentInputError(
            f"ExecutiveSummaryAgent step '{step.step_id}' is missing a 'report_document' object in step.inputs."
        )
    try:
        report_document = ReportDocument.model_validate(raw_report)
    except ValidationError as exc:
        raise InvalidAgentInputError(
            f"ExecutiveSummaryAgent step '{step.step_id}' has an invalid 'report_document': {exc}"
        ) from exc

    raw_browser_result = step.inputs.get("browser_agent_result")
    browser_result: BrowserAgentResult | None = None
    if raw_browser_result is not None:
        if not isinstance(raw_browser_result, dict):
            raise InvalidAgentInputError(
                f"ExecutiveSummaryAgent step '{step.step_id}' has a 'browser_agent_result' that is not an object."
            )
        try:
            browser_result = BrowserAgentResult.model_validate(raw_browser_result)
        except ValidationError as exc:
            raise InvalidAgentInputError(
                f"ExecutiveSummaryAgent step '{step.step_id}' has an invalid 'browser_agent_result': {exc}"
            ) from exc

    dataset_metadata = step.inputs.get("dataset_metadata") or {}
    if not isinstance(dataset_metadata, dict):
        raise InvalidAgentInputError(
            f"ExecutiveSummaryAgent step '{step.step_id}' has a 'dataset_metadata' that is not an object."
        )

    analysis_metadata = step.inputs.get("analysis_metadata") or {}
    if not isinstance(analysis_metadata, dict):
        raise InvalidAgentInputError(
            f"ExecutiveSummaryAgent step '{step.step_id}' has an 'analysis_metadata' that is not an object."
        )

    return report_document, browser_result, dataset_metadata, analysis_metadata
