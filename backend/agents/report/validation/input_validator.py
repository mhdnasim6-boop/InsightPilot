"""Validates ReportAgent's own inputs before ReportService is called.

Unlike File/SQL/BrowserAgent, ReportAgent's inputs are already-computed
pipeline outputs (``BusinessDataset``/``CleaningOutcome``/
``AnalysisResult``/``VisualizationResult``/``BrowserAgentResult``), not
raw references — so ``step.inputs`` carries each as a JSON-shaped dict
(exactly what ``result.model_dump(mode="json")`` produces), and this
module's job is turning those dicts back into real Pydantic models
before ``ReportAgent`` touches them. Only ``dataset`` is required,
mirroring ``ReportService.build_report()``'s own required parameter;
every other pipeline output is optional, mirroring ``ReportBuilder``'s
own tolerance for missing inputs.
"""

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from backend.agents.browser.models.result import BrowserAgentResult
from backend.agents.file.exceptions.errors import InvalidAgentInputError
from backend.analysis.models.result import AnalysisResult
from backend.cleaning.models.outcome import CleaningOutcome
from backend.ingestion.models.dataset import BusinessDataset
from backend.planning.models.step import ExecutionStep
from backend.reporting.templates.report_template import ReportTemplateType
from backend.visualization.models.result import VisualizationResult

_ModelT = TypeVar("_ModelT", bound=BaseModel)


def validate_agent_input(
    step: ExecutionStep, session_id: str | None
) -> tuple[
    BusinessDataset,
    CleaningOutcome | None,
    AnalysisResult | None,
    VisualizationResult | None,
    BrowserAgentResult | None,
    ReportTemplateType,
    dict[str, object],
]:
    """Check that ``step``/``session_id`` carry what ReportAgent needs to run.

    Returns ``(dataset, cleaning_outcome, analysis_result,
    visualization_result, browser_result, template_type, report_config)``.
    Raises ``InvalidAgentInputError`` if the session is missing,
    ``dataset`` is absent or malformed, any present optional field is the
    wrong shape, or an explicit ``template_type`` isn't a recognized
    value.
    """
    if not session_id or not session_id.strip():
        raise InvalidAgentInputError(f"ReportAgent step '{step.step_id}' has no session_id.")

    raw_dataset = step.inputs.get("dataset")
    if not isinstance(raw_dataset, dict):
        raise InvalidAgentInputError(f"ReportAgent step '{step.step_id}' is missing a 'dataset' object in step.inputs.")
    dataset = _parse_model(step, "dataset", raw_dataset, BusinessDataset)

    cleaning_outcome = _parse_optional(step, "cleaning_outcome", CleaningOutcome)
    analysis_result = _parse_optional(step, "analysis_result", AnalysisResult)
    visualization_result = _parse_optional(step, "visualization_result", VisualizationResult)
    browser_result = _parse_optional(step, "browser_agent_result", BrowserAgentResult)

    raw_config = step.inputs.get("report_config") or {}
    if not isinstance(raw_config, dict):
        raise InvalidAgentInputError(f"ReportAgent step '{step.step_id}' has a 'report_config' that is not an object.")

    template_type = _parse_template_type(step, raw_config.get("template_type"))

    return dataset, cleaning_outcome, analysis_result, visualization_result, browser_result, template_type, raw_config


def _parse_optional(step: ExecutionStep, key: str, model: type[_ModelT]) -> _ModelT | None:
    raw = step.inputs.get(key)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise InvalidAgentInputError(f"ReportAgent step '{step.step_id}' has a '{key}' that is not an object.")
    return _parse_model(step, key, raw, model)


def _parse_model(step: ExecutionStep, key: str, raw: dict[str, object], model: type[_ModelT]) -> _ModelT:
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise InvalidAgentInputError(f"ReportAgent step '{step.step_id}' has an invalid '{key}': {exc}") from exc


def _parse_template_type(step: ExecutionStep, raw: object) -> ReportTemplateType:
    if raw is None:
        return ReportTemplateType.BUSINESS_REPORT
    try:
        return ReportTemplateType(raw)
    except ValueError as exc:
        raise InvalidAgentInputError(
            f"ReportAgent step '{step.step_id}' has an unknown report_config.template_type '{raw}'."
        ) from exc
