"""Request body for POST /api/v1/agents/file/execute."""

from pydantic import BaseModel

from backend.planning.models.step import ExecutionStep


class FileAgentExecuteRequest(BaseModel):
    """Everything FileAgent needs to run: an ExecutionStep and a session.

    ``step.inputs`` carries ``dataset_reference`` (required) and
    ``generate_report`` (optional, default False) — the same channel
    ``PlanExecutor`` already uses to flow step-specific parameters into
    the orchestration graph, so a direct REST call and a graph-driven
    run read these the same way.
    """

    step: ExecutionStep
    session_id: str | None = None
