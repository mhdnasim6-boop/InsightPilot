"""Timeline export for an ExecutionPlan: a linear, ordered view of its steps."""

from pydantic import BaseModel, Field

from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.plan import ExecutionPlan


class TimelineEntry(BaseModel):
    """A single step's position in a plan's timeline."""

    step_id: str
    name: str
    order_index: int
    depends_on: list[str] = Field(default_factory=list)
    status: ExecutionStatus


class PlanTimeline(BaseModel):
    """A linear, ordered view of a plan's steps."""

    plan_id: str
    entries: list[TimelineEntry] = Field(default_factory=list)


def generate_plan_timeline(plan: ExecutionPlan, execution_order: list[str] | None = None) -> PlanTimeline:
    """Build a timeline from a plan's steps, in ``execution_order`` (or declaration order)."""
    order = execution_order or [step.step_id for step in plan.steps]
    steps_by_id = {step.step_id: step for step in plan.steps}

    entries = [
        TimelineEntry(
            step_id=step_id,
            name=steps_by_id[step_id].name,
            order_index=index,
            depends_on=list(steps_by_id[step_id].dependencies),
            status=steps_by_id[step_id].status,
        )
        for index, step_id in enumerate(order)
    ]
    return PlanTimeline(plan_id=plan.plan_id, entries=entries)
