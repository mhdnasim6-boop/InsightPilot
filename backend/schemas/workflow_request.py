"""Request models for /api/v1/workflows.

Mirrors every other phase's own ``backend/schemas/*_request.py`` module —
REST-only shapes, distinct from the workflow domain's own
``backend/workflows/models/``.
"""

from pydantic import BaseModel, Field

from backend.workflows.models.workflow_step import WorkflowStep


class CreateWorkflowRequest(BaseModel):
    """Body for POST /workflows — either an ``objective`` (delegates to the real PlannerAgent)
    or explicit ``name``/``steps`` (an authored workflow), never both required at once."""

    objective: str | None = None
    name: str | None = None
    description: str = ""
    steps: list[WorkflowStep] | None = None
    tags: list[str] = Field(default_factory=list)
    session_id: str | None = None


class ExecuteWorkflowRequest(BaseModel):
    """Body for POST /workflows/{id}/execute and .../resume."""

    session_id: str | None = None


class CloneWorkflowRequest(BaseModel):
    """Body for POST /workflows/{id}/clone."""

    new_name: str | None = None
