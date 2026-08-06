"""ResourceOptimizer: advisory actions for memory/AI/tool/plugin/security bottlenecks.

Covers ``MEMORY_UTILIZATION``, ``AI_USAGE``, ``TOOL_USAGE``,
``PLUGIN_USAGE``, and ``SECURITY_OVERHEAD`` — all "how much of a shared
resource is this platform consuming" concerns.
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

_HANDLED_CATEGORIES = frozenset({
    BottleneckCategory.MEMORY_UTILIZATION, BottleneckCategory.AI_USAGE, BottleneckCategory.TOOL_USAGE,
    BottleneckCategory.PLUGIN_USAGE, BottleneckCategory.SECURITY_OVERHEAD,
})

_IMPACT_BY_SEVERITY: dict[BottleneckSeverity, Literal["low", "medium", "high"]] = {
    BottleneckSeverity.LOW: "low",
    BottleneckSeverity.MEDIUM: "medium",
    BottleneckSeverity.HIGH: "high",
    BottleneckSeverity.CRITICAL: "high",
}

_SUGGESTIONS: dict[BottleneckCategory, str] = {
    BottleneckCategory.MEMORY_UTILIZATION: (
        "Review the Memory page's own statistics — consider applying a RetentionPolicy to "
        "prune low-importance or stale memories (a human decision; nothing here deletes anything)."
    ),
    BottleneckCategory.AI_USAGE: (
        "Review AI call latency in the Observability page's own metrics — consider a "
        "different provider/model for latency-sensitive agents."
    ),
    BottleneckCategory.TOOL_USAGE: (
        "Review the named tool's own recent traces in Observability's Trace Viewer to "
        "diagnose the specific failure or latency cause."
    ),
    BottleneckCategory.PLUGIN_USAGE: (
        "Review the named tool's own traces — if it is plugin-contributed, check the "
        "Plugins page for its current state and consider reloading or disabling it."
    ),
    BottleneckCategory.SECURITY_OVERHEAD: (
        "Review the Security page's own audit log — a high event volume is usually "
        "informational, but worth confirming nothing is retrying abnormally."
    ),
}


class ResourceOptimizer:
    """Turns memory/AI/tool/plugin/security Bottlenecks into advisory actions."""

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
