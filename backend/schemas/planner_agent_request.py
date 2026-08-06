"""Request bodies for the Planner Agent's REST endpoints."""

from pydantic import BaseModel

from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep


class PlannerAgentExecuteRequest(BaseModel):
    """Everything PlannerAgent needs to run: an ExecutionStep and a session.

    ``step.inputs`` carries ``user_request`` (required) and, all
    optional: ``conversation_summary``, ``uploaded_datasets`` (a list of
    ``BusinessDataset``-shaped dicts), ``available_sql_connections``,
    ``available_browser_context``, ``existing_reports``, and
    ``user_preferences`` — the same channel ``PlanExecutor`` already uses
    to flow step-specific parameters into the orchestration graph,
    mirroring ``ReportAgentExecuteRequest``. Agent discovery itself is
    never taken from the request — PlannerAgent always reads the live
    orchestration graph.
    """

    step: ExecutionStep
    session_id: str | None = None


class PlanActionRequest(BaseModel):
    """A previously generated (or user-edited) ExecutionPlan, for preview/validate/explain/execute."""

    plan: ExecutionPlan
