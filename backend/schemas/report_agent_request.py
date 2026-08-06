"""Request body for POST /api/v1/agents/report/execute."""

from pydantic import BaseModel

from backend.planning.models.step import ExecutionStep


class ReportAgentExecuteRequest(BaseModel):
    """Everything ReportAgent needs to run: an ExecutionStep and a session.

    ``step.inputs`` carries ``dataset`` (a ``BusinessDataset``-shaped
    dict, required) and, all optional: ``cleaning_outcome``,
    ``analysis_result``, ``visualization_result`` (each shaped like the
    matching pipeline model's own JSON form), ``browser_agent_result`` (a
    ``BrowserAgentResult``-shaped dict), and ``report_config``
    (``{"template_type", "theme", "title", "subtitle", "author"}``, all
    optional) — the same channel ``PlanExecutor`` already uses to flow
    step-specific parameters into the orchestration graph, mirroring
    ``BrowserAgentExecuteRequest``.
    """

    step: ExecutionStep
    session_id: str | None = None
