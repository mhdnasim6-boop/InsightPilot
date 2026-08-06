"""WorkflowOptimizer: two existing optimizers, delegated to in sequence —
never a third, workflow-specific optimization algorithm.

1. ``adaptive_optimize()`` — AdaptivePlanningService's deterministic,
   evidence-backed pass (reflections/execution history/collaboration
   history/memory), the same one Planner runs before validation
   (Phase 32).
2. ``structural_optimize()`` — the existing structural PlanOptimizer
   (via PlanningService.optimize()), advancing VALIDATED -> READY —
   required before ExecutionService will accept the plan at all.
"""

from backend.adaptive.models.optimization_result import OptimizationResult
from backend.adaptive.services.adaptive_planning_service import AdaptivePlanningService
from backend.planning.models.plan import ExecutionPlan
from backend.services.planning_service import PlanningService


class WorkflowOptimizer:
    """Runs a plan through the adaptive optimizer, then the structural one."""

    def __init__(self, adaptive_planning_service: AdaptivePlanningService, planning_service: PlanningService) -> None:
        self._adaptive_planning_service = adaptive_planning_service
        self._planning_service = planning_service

    def adaptive_optimize(self, plan: ExecutionPlan, session_id: str | None) -> OptimizationResult:
        """Analyze ``plan`` against historical evidence, remember the result, and return it —
        ``result.optimized_plan`` is what the caller should continue with."""
        return self._adaptive_planning_service.optimize(plan, session_id)

    def structural_optimize(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Advance a VALIDATED plan to READY via the real, deterministic PlanOptimizer."""
        return self._planning_service.optimize(plan)
