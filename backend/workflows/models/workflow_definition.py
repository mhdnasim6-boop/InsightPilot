"""WorkflowDefinition: the reusable "recipe" — a named, described, tagged
list of WorkflowSteps. What gets cloned, versioned, and (via
WorkflowBuilder) converted into a real ExecutionPlan.
"""

from pydantic import BaseModel, ConfigDict, Field

from backend.workflows.models.workflow_step import WorkflowStep


class WorkflowDefinition(BaseModel):
    """A named DAG recipe: what to run and how the steps depend on each other."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    steps: list[WorkflowStep] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
