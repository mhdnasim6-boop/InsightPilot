"""The default, purely structural PlanOptimizer implementation."""

from typing import Any

from backend.planning.models.plan import ExecutionPlan
from backend.planning.optimizer.base import PlanOptimizer
from backend.planning.validator.topology import topological_order
from backend.utils.time import utc_now


class DefaultPlanOptimizer(PlanOptimizer):
    """Reorders steps into a valid execution order and dedupes list-valued metadata.

    Deliberately not AI-aware: no cost-based scheduling, no batching
    decisions. Those are future optimization hooks built on top of this
    default, not part of it.
    """

    def optimize(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Return a copy of ``plan`` with steps reordered and metadata deduplicated."""
        order = topological_order(plan.steps)
        steps_by_id = {step.step_id: step for step in plan.steps}
        reordered_steps = [steps_by_id[step_id] for step_id in order]

        return plan.model_copy(
            update={
                "steps": reordered_steps,
                "metadata": self._dedupe_metadata(plan.metadata),
                "updated_at": utc_now(),
            }
        )

    def _dedupe_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Remove duplicate entries from any list-valued metadata field, preserving order."""
        deduped: dict[str, Any] = {}
        for key, value in metadata.items():
            if isinstance(value, list):
                unique: list[Any] = []
                for item in value:
                    if item not in unique:
                        unique.append(item)
                deduped[key] = unique
            else:
                deduped[key] = value
        return deduped
