"""WorkflowOptimizer: advisory actions for workflow-structure bottlenecks.

Covers ``WORKFLOW_EFFICIENCY`` and ``PARALLELISM`` — how a workflow itself
is *structured*, as opposed to how execution infrastructure is
performing (``execution_optimizer.py``) or how resources are consumed
(``resource_optimizer.py``). Not to be confused with
``backend.workflows.planner.workflow_optimizer.WorkflowOptimizer``
(Phase 36) — that one actually restructures an ``ExecutionPlan``; this
one only ever *suggests* a restructuring, never performs one.
"""

from typing import Literal

from backend.autonomous.models.bottleneck import (
    Bottleneck,
    BottleneckCategory,
    BottleneckSeverity,
)
from backend.autonomous.models.optimization_action import OptimizationAction
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

_HANDLED_CATEGORIES = frozenset({BottleneckCategory.WORKFLOW_EFFICIENCY, BottleneckCategory.PARALLELISM})

_IMPACT_BY_SEVERITY: dict[BottleneckSeverity, Literal["low", "medium", "high"]] = {
    BottleneckSeverity.LOW: "low",
    BottleneckSeverity.MEDIUM: "medium",
    BottleneckSeverity.HIGH: "high",
    BottleneckSeverity.CRITICAL: "high",
}

_SUGGESTIONS: dict[BottleneckCategory, str] = {
    BottleneckCategory.WORKFLOW_EFFICIENCY: (
        "Review the Workflows page's own execution history and statistics — a high failure "
        "rate or long average duration usually traces back to one or two specific steps."
    ),
    BottleneckCategory.PARALLELISM: (
        "Review the workflow's own dependency graph — steps with no dependency on each "
        "other can run concurrently; AdaptivePlanningService's own structural optimizer "
        "already reorders independent steps where it safely can."
    ),
}


class WorkflowOptimizer:
    """Turns workflow-efficiency and parallelism Bottlenecks into advisory actions."""

    def generate_actions(self, bottlenecks: list[Bottleneck]) -> list[OptimizationAction]:
        return [self._to_action(b) for b in bottlenecks if b.category in _HANDLED_CATEGORIES]

    def _to_action(self, bottleneck: Bottleneck) -> OptimizationAction:
        return OptimizationAction(
            action_id=generate_id(), bottleneck_id=bottleneck.bottleneck_id, category=bottleneck.category,
            title=f"Address: {bottleneck.title}",
            description=_SUGGESTIONS.get(bottleneck.category, "Review this finding in the Autonomous page."),
            estimated_impact=_IMPACT_BY_SEVERITY[bottleneck.severity],
            created_at=utc_now(),
        )
