"""ExecutionOptimizer: advisory actions for execution/approval/reflection/worker/cluster bottlenecks.

Covers ``EXECUTION_EFFICIENCY``, ``APPROVAL_BOTTLENECK``, ``REFLECTION_TRENDS``,
``WORKER_UTILIZATION``, and ``CLUSTER_UTILIZATION`` — the categories
concerned with how well execution *infrastructure* (Phase 27's engine,
Phase 38's workers, Phase 39's clusters) is performing, as opposed to how
a workflow is *structured* (``workflow_optimizer.py``) or how *resources*
are consumed (``resource_optimizer.py``). Every action produced is purely
advisory — see this package's own top-level docstring.
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

_IMPACT_BY_SEVERITY: dict[BottleneckSeverity, Literal["low", "medium", "high"]] = {
    BottleneckSeverity.LOW: "low",
    BottleneckSeverity.MEDIUM: "medium",
    BottleneckSeverity.HIGH: "high",
    BottleneckSeverity.CRITICAL: "high",
}

_HANDLED_CATEGORIES = frozenset({
    BottleneckCategory.EXECUTION_EFFICIENCY, BottleneckCategory.APPROVAL_BOTTLENECK,
    BottleneckCategory.REFLECTION_TRENDS, BottleneckCategory.WORKER_UTILIZATION,
    BottleneckCategory.CLUSTER_UTILIZATION,
})

_SUGGESTIONS: dict[BottleneckCategory, str] = {
    BottleneckCategory.EXECUTION_EFFICIENCY: (
        "Review recently failed/slow steps in Observability's Trace Viewer and consider "
        "tuning retry policy or step timeouts for the agents involved."
    ),
    BottleneckCategory.APPROVAL_BOTTLENECK: (
        "Review the active ApprovalPolicy — consider narrowing which node names require "
        "approval, or notify approvers proactively when a queue is building up."
    ),
    BottleneckCategory.REFLECTION_TRENDS: (
        "Review recent reflections' own recommendations in the Reflection page — a "
        "declining score trend usually points to a specific, recurring failure pattern."
    ),
    BottleneckCategory.WORKER_UTILIZATION: (
        "Review the Distributed page — consider registering additional workers, or "
        "investigating why existing workers went OFFLINE/FAILED."
    ),
    BottleneckCategory.CLUSTER_UTILIZATION: (
        "Review the Federation page — consider registering additional clusters, or "
        "investigating why existing clusters are unavailable."
    ),
}


class ExecutionOptimizer:
    """Turns execution/approval/reflection/worker/cluster Bottlenecks into advisory actions."""

    def generate_actions(self, bottlenecks: list[Bottleneck]) -> list[OptimizationAction]:
        return [
            self._to_action(bottleneck)
            for bottleneck in bottlenecks
            if bottleneck.category in _HANDLED_CATEGORIES
        ]

    def _to_action(self, bottleneck: Bottleneck) -> OptimizationAction:
        return OptimizationAction(
            action_id=generate_id(), bottleneck_id=bottleneck.bottleneck_id, category=bottleneck.category,
            title=f"Address: {bottleneck.title}",
            description=_SUGGESTIONS.get(bottleneck.category, "Review this finding in the Autonomous page."),
            estimated_impact=_IMPACT_BY_SEVERITY[bottleneck.severity],
            created_at=utc_now(),
        )
