"""RecoveryStrategy: a static catalog of named, advisory-only recovery strategies.

Pure data — no method here executes anything. ``SelfHealingEngine`` uses
this catalog to give each candidate recommendation a stable,
human-readable ``strategy_name`` and a richer rationale than the
optimizer layer's own generic per-category suggestion text.
"""

from backend.autonomous.models.bottleneck import BottleneckCategory

_STRATEGY_NAMES: dict[BottleneckCategory, str] = {
    BottleneckCategory.EXECUTION_EFFICIENCY: "review_execution_timing",
    BottleneckCategory.WORKFLOW_EFFICIENCY: "review_workflow_structure",
    BottleneckCategory.PARALLELISM: "review_step_dependencies",
    BottleneckCategory.WORKER_UTILIZATION: "review_worker_fleet",
    BottleneckCategory.CLUSTER_UTILIZATION: "review_cluster_fleet",
    BottleneckCategory.APPROVAL_BOTTLENECK: "review_approval_policy",
    BottleneckCategory.REFLECTION_TRENDS: "review_reflection_history",
    BottleneckCategory.MEMORY_UTILIZATION: "review_retention_policy",
    BottleneckCategory.AI_USAGE: "review_ai_provider_choice",
    BottleneckCategory.TOOL_USAGE: "review_tool_reliability",
    BottleneckCategory.PLUGIN_USAGE: "review_plugin_health",
    BottleneckCategory.SECURITY_OVERHEAD: "review_audit_activity",
}

_STRATEGY_RATIONALE: dict[BottleneckCategory, str] = {
    BottleneckCategory.EXECUTION_EFFICIENCY: "Slow or failing executions compound: a step's own retry/timeout tuning is the fastest lever a human operator has.",
    BottleneckCategory.WORKFLOW_EFFICIENCY: "A workflow's own failure/duration trend usually traces back to one or two specific steps worth isolating.",
    BottleneckCategory.PARALLELISM: "Independent steps running sequentially waste wall-clock time with no correctness benefit.",
    BottleneckCategory.WORKER_UTILIZATION: "An unhealthy or saturated worker fleet directly limits how much real work the platform can credit and complete.",
    BottleneckCategory.CLUSTER_UTILIZATION: "An unhealthy or saturated cluster fleet directly limits federation-wide routing options.",
    BottleneckCategory.APPROVAL_BOTTLENECK: "Slow approvals delay every downstream step in a paused execution, not just the gated one.",
    BottleneckCategory.REFLECTION_TRENDS: "A declining reflection score trend is the platform's own historical judgment that something is degrading.",
    BottleneckCategory.MEMORY_UTILIZATION: "Unbounded memory growth eventually affects retrieval relevance and storage cost.",
    BottleneckCategory.AI_USAGE: "AI latency directly adds to every agent call that depends on it.",
    BottleneckCategory.TOOL_USAGE: "A consistently failing or slow tool degrades every agent that depends on it.",
    BottleneckCategory.PLUGIN_USAGE: "A plugin-contributed tool's own failures are otherwise easy to miss among first-party tool traces.",
    BottleneckCategory.SECURITY_OVERHEAD: "Audit volume is usually benign, but a spike is worth confirming isn't a retry storm.",
}


class RecoveryStrategyCatalog:
    """Read-only lookup of a stable strategy_name and rationale per BottleneckCategory."""

    def strategy_name_for(self, category: BottleneckCategory) -> str:
        return _STRATEGY_NAMES.get(category, f"review_{category.value}")

    def rationale_for(self, category: BottleneckCategory) -> str:
        return _STRATEGY_RATIONALE.get(category, "Review this finding in the Autonomous page for more detail.")
