"""Estimation snapshot for an ExecutionPlan.

Infrastructure only — every field here is either copied straight from
the plan or left ``None``. Real estimation (token/cost prediction,
parallelism analysis) is future work for the Planner/optimizer, once
real nodes exist to measure against.
"""

from pydantic import BaseModel

from backend.planning.models.plan import ExecutionPlan


class PlanMetrics(BaseModel):
    """A read-only snapshot of a plan's estimate fields, plus room for future ones."""

    plan_id: str
    estimated_tokens: int | None = None
    estimated_duration: float | None = None
    estimated_cost: float | None = None
    estimated_parallelism: int | None = None

    @classmethod
    def from_plan(cls, plan: ExecutionPlan) -> "PlanMetrics":
        """Snapshot the estimate fields already present on a plan. No calculation performed."""
        return cls(
            plan_id=plan.plan_id,
            estimated_tokens=plan.estimated_tokens,
            estimated_duration=plan.estimated_duration,
            estimated_cost=plan.estimated_cost,
        )
