"""Workflow: the top-level, persisted resource — identity + definition +
current status. What POST /workflows creates and GET /workflows/{id}
returns.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.workflows.models.workflow_definition import WorkflowDefinition
from backend.workflows.models.workflow_status import WorkflowStatus


class Workflow(BaseModel):
    """One workflow's identity, its definition, and its current lifecycle status."""

    model_config = ConfigDict(frozen=True)

    workflow_id: str
    definition: WorkflowDefinition
    status: WorkflowStatus = WorkflowStatus.DRAFT
    plan_id: str | None = None
    version: int = 1
    cloned_from: str | None = None
    created_at: datetime
    updated_at: datetime
