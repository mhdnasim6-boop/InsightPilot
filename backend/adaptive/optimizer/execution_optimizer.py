"""execution_optimizer: reorders ExecutionPlan.steps into a valid, dependency-safe
order, plus an advisory parallelization decision when historical efficiency
has been poor.

Reordering reuses ``topological_order()`` (Phase 5's own Kahn's-algorithm
implementation, already the sole source of ordering truth for
``PlanValidator``/``DependencyResolver``) directly — never a second
ordering algorithm. This mutation is always safe: a topological order is
valid by definition, so reordering the *list* never changes what the DAG
scheduler is actually allowed to run concurrently (that is governed by
``dependencies`` alone, untouched here).
"""

from backend.adaptive.models.optimization_result import (
    OptimizationDecision,
    OptimizationDecisionCategory,
)
from backend.adaptive.models.planning_context import PlanningContext
from backend.adaptive.optimizer.planner_optimizer import build_decision
from backend.planning.models.plan import ExecutionPlan
from backend.planning.validator.topology import topological_order


def optimize_execution_order(
    plan: ExecutionPlan, context: PlanningContext
) -> tuple[ExecutionPlan, list[OptimizationDecision]]:
    """Reorder steps topologically, plus flag a repeated parallelization bottleneck."""
    decisions: list[OptimizationDecision] = []

    ordered_ids = topological_order(plan.steps)
    current_ids = [step.step_id for step in plan.steps]
    updated_plan = plan
    if ordered_ids != current_ids:
        steps_by_id = {step.step_id: step for step in plan.steps}
        updated_plan = plan.model_copy(update={"steps": [steps_by_id[step_id] for step_id in ordered_ids]})
        decisions.append(
            build_decision(
                OptimizationDecisionCategory.REORDER,
                True,
                "Reordered steps into a dependency-safe execution order.",
                "Steps were not already declared in a valid topological order.",
            )
        )

    if context.execution_patterns.get("bottleneck_detected"):
        decisions.append(
            build_decision(
                OptimizationDecisionCategory.PARALLELIZATION,
                False,
                "Review step dependencies for unnecessary serialization.",
                f"Average efficiency score was {context.execution_patterns['average_efficiency_score']:.0f}/100 "
                f"across {context.execution_patterns['sample_size']} prior execution(s).",
                context.execution_patterns.get("low_efficiency_count", 0),
            )
        )

    return updated_plan, decisions
