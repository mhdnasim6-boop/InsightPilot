"""Request body for POST /execution/start."""

from pydantic import BaseModel

from backend.planning.models.plan import ExecutionPlan


class ExecutionStartRequest(BaseModel):
    """A READY ExecutionPlan to run as a dependency-aware, parallel DAG."""

    plan: ExecutionPlan
    session_id: str | None = None
