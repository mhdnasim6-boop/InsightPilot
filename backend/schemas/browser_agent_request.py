"""Request body for POST /api/v1/agents/browser/execute."""

from pydantic import BaseModel

from backend.planning.models.step import ExecutionStep


class BrowserAgentExecuteRequest(BaseModel):
    """Everything BrowserAgent needs to run: an ExecutionStep and a session.

    ``step.inputs`` carries any combination of ``search_request`` (a
    single free-text string), ``companies``/``industries``/``products``/
    ``keywords`` (each a list of strings) — all optional. A step with
    none of these returns a SKIPPED result rather than an error, the
    same channel ``PlanExecutor`` already uses to flow step-specific
    parameters into the orchestration graph, mirroring
    ``SQLAgentExecuteRequest``.
    """

    step: ExecutionStep
    session_id: str | None = None
