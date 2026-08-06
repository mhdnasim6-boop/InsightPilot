"""Response shapes for the Planner Agent's preview/validate/explain REST endpoints.

Each is a thin reshape of what ``PlanningService``/``ExecutionPlan``
already expose — no new plan-inspection logic lives here.
"""

from pydantic import BaseModel, Field

from backend.planning.models.plan import ExecutionPlan
from backend.planning.validator.result import PlanValidationResult
from backend.planning.visualization.timeline import PlanTimeline


class PlanPreview(BaseModel):
    """A plan rendered three ways at once: Mermaid flowchart, JSON, and a linear timeline."""

    mermaid: str
    json_export: str
    timeline: PlanTimeline


class PlanValidationResponse(BaseModel):
    """A plan (possibly advanced to VALIDATED) alongside the validation findings that produced that status."""

    plan: ExecutionPlan
    validation: PlanValidationResult


class PlanExplanationStep(BaseModel):
    """Why one step's agent was selected, in plan order."""

    step_id: str
    name: str
    node_name: str
    reasoning: str
    depends_on: list[str] = Field(default_factory=list)


class PlanExplanation(BaseModel):
    """A plan's goal and confidence alongside a per-step explanation of why each agent was selected.

    ``reasoning`` for each step is that step's own ``description`` — the
    Planner is prompted to write that field as the "why", so this works
    uniformly whether the plan was just generated or edited by a user
    afterward; there's no separate stored rationale to fall out of sync.
    """

    goal: str | None
    confidence: float | None
    estimated_duration: float | None
    steps: list[PlanExplanationStep] = Field(default_factory=list)

    @classmethod
    def from_plan(cls, plan: ExecutionPlan) -> "PlanExplanation":
        """Reshape an ExecutionPlan into its explanation view — no new data, just a different lens."""
        return cls(
            goal=plan.goal,
            confidence=plan.confidence,
            estimated_duration=plan.estimated_duration,
            steps=[
                PlanExplanationStep(
                    step_id=step.step_id,
                    name=step.name,
                    node_name=step.node_name,
                    reasoning=step.description or "No rationale was recorded for this step.",
                    depends_on=step.dependencies,
                )
                for step in plan.steps
            ],
        )
