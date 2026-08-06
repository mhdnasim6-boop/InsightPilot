"""Request body for POST /api/v1/agents/executive-summary/execute."""

from pydantic import BaseModel

from backend.planning.models.step import ExecutionStep


class ExecutiveSummaryExecuteRequest(BaseModel):
    """Everything ExecutiveSummaryAgent needs to run: an ExecutionStep and a session.

    ``step.inputs`` carries ``report_document`` (a ``ReportDocument``-shaped
    dict, required) and, all optional: ``browser_agent_result`` (a
    ``BrowserAgentResult``-shaped dict), ``dataset_metadata``, and
    ``analysis_metadata`` (small facts dicts, not full objects) — the
    same channel ``PlanExecutor`` already uses to flow step-specific
    parameters into the orchestration graph, mirroring
    ``ReportAgentExecuteRequest``.
    """

    step: ExecutionStep
    session_id: str | None = None
