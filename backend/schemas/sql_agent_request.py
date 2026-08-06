"""Request body for POST /api/v1/agents/sql/execute."""

from pydantic import BaseModel

from backend.planning.models.step import ExecutionStep


class SQLAgentExecuteRequest(BaseModel):
    """Everything SQLAgent needs to run: an ExecutionStep and a session.

    ``step.inputs`` carries ``connection`` (a ``SQLConnectionConfig``-shaped
    dict, required), exactly one of ``table_name``/``query`` (required),
    ``dataset_name`` (optional), and ``generate_report`` (optional,
    default False) — the same channel ``PlanExecutor`` already uses to
    flow step-specific parameters into the orchestration graph,
    mirroring ``FileAgentExecuteRequest``.
    """

    step: ExecutionStep
    session_id: str | None = None
