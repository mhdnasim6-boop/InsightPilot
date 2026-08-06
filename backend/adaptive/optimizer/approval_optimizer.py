"""approval_optimizer: advisory-only approval-friction decisions.

Never mutates ``ExecutionPlan`` — approval gating is a global,
node-name-keyed policy owned by ``ApprovalPolicyService``
(``backend.approval``), not a per-plan field ``ExecutionPlan`` even has.
Silently changing that global policy as a side effect of optimizing one
plan would be a surprising, blast-radius-mismatched action, so this
module only ever produces an advisory ``OptimizationDecision``.
"""

from backend.adaptive.models.optimization_result import (
    OptimizationDecision,
    OptimizationDecisionCategory,
)
from backend.adaptive.models.planning_context import PlanningContext
from backend.adaptive.optimizer.planner_optimizer import (
    PATTERN_THRESHOLD,
    build_decision,
)


def generate_approval_decisions(context: PlanningContext) -> list[OptimizationDecision]:
    """Flag repeated approval friction, if any, as an advisory decision."""
    approval_delay_count = context.reflection_patterns.get("approval_delay_count", 0)
    if approval_delay_count < PATTERN_THRESHOLD:
        return []

    return [
        build_decision(
            OptimizationDecisionCategory.APPROVAL_REDUCTION,
            False,
            "Consider reducing approval gates for this workflow.",
            f"Approval friction (rejections or long delays) was flagged in {approval_delay_count} prior "
            "reflection(s).",
            approval_delay_count,
        )
    ]
