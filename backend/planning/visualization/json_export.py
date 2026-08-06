"""JSON export for an ExecutionPlan."""

from backend.planning.models.plan import ExecutionPlan


def generate_plan_json(plan: ExecutionPlan) -> str:
    """Serialize a plan to a stable, indented JSON string."""
    return plan.model_dump_json(indent=2)
