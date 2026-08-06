"""RecommendationEngine: turns the other analyzers' output into deterministic,
actionable Recommendations.

Not itself named in the phase's own literal folder tree (only
``models/recommendation.py`` — the *shape* — was listed), but generating
recommendations is its own explicit spec section, and "recommendation
generation" is its own listed test category — it needs a directly
importable, directly testable home. Added here, alongside its sibling
analyzers, the same way Phase 30 added ``artifact_exchange.py`` beyond
its own literal ``models/`` list for an analogous reason.

Every rule below reacts to one concrete fact already computed by another
analyzer — never a guess, never an LLM call.
"""

from typing import Any

from backend.reflection.models.recommendation import (
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
)
from backend.utils.ids import generate_id

_APPROVAL_DELAY_THRESHOLD_SECONDS = 60.0


def generate_recommendations(
    execution_summary: dict[str, Any],
    tool_summary: dict[str, Any],
    approval_summary: dict[str, Any],
    memory_summary: dict[str, Any],
    collaboration_summary: dict[str, Any],
) -> list[Recommendation]:
    """Derive every applicable Recommendation from the other analyzers' own output."""
    recommendations: list[Recommendation] = []

    for tool_name in tool_summary["failed_tools"]:
        recommendations.append(
            _recommendation(
                RecommendationCategory.RETRY,
                f"Retry the failed '{tool_name}' step next time.",
                RecommendationPriority.HIGH,
                f"'{tool_name}' failed during this execution.",
            )
        )

    if "file_agent" in execution_summary["failed_agents"]:
        recommendations.append(
            _recommendation(
                RecommendationCategory.TOOL_CHOICE,
                "Consider using SQLAgent instead of FileAgent if the data is available in a database connection.",
                RecommendationPriority.MEDIUM,
                "FileAgent failed during this execution.",
            )
        )

    if approval_summary["rejected_count"] > 0 or (
        approval_summary["total_approvals"] > 0
        and approval_summary["average_delay_seconds"] > _APPROVAL_DELAY_THRESHOLD_SECONDS
    ):
        recommendations.append(
            _recommendation(
                RecommendationCategory.APPROVAL_POLICY,
                "Consider relaxing the approval policy for this workflow.",
                RecommendationPriority.MEDIUM,
                f"{approval_summary['rejected_count']} rejection(s) and an average approval "
                f"delay of {approval_summary['average_delay_seconds']:.0f}s across "
                f"{approval_summary['total_approvals']} gate(s).",
            )
        )

    if execution_summary["agent_count"] > 1 and execution_summary["slow_agents"]:
        recommendations.append(
            _recommendation(
                RecommendationCategory.PARALLELIZATION,
                "Run independent agents concurrently via the Execution/Collaboration engine instead of sequentially.",
                RecommendationPriority.MEDIUM,
                f"Slow agent(s) detected: {', '.join(execution_summary['slow_agents'])}.",
            )
        )

    if memory_summary["reused_memory"]:
        recommendations.append(
            _recommendation(
                RecommendationCategory.CACHING,
                "Relevant prior results were found — consider reusing/caching them directly instead of recomputing.",
                RecommendationPriority.LOW,
                f"{memory_summary['relevant_prior_count']} relevant prior memory item(s) existed for this request.",
            )
        )
    elif execution_summary["overall_success"]:
        recommendations.append(
            _recommendation(
                RecommendationCategory.MEMORY_REUSE,
                "Store and reuse this execution's results via Memory for similar future requests.",
                RecommendationPriority.LOW,
                "No relevant prior memory was found for this request.",
            )
        )

    if "browser_agent" in execution_summary["completed_agents"] and "search_web" not in tool_summary["calls_per_tool"]:
        recommendations.append(
            _recommendation(
                RecommendationCategory.OTHER,
                "Avoid delegating to BrowserAgent when there is no external research need.",
                RecommendationPriority.LOW,
                "BrowserAgent ran but made no search_web calls.",
            )
        )

    if collaboration_summary["used_collaboration"] and collaboration_summary["failed_subtasks"] > 0:
        recommendations.append(
            _recommendation(
                RecommendationCategory.RETRY,
                "Review and retry the failed collaboration subtask(s) before relying on this session's outcome.",
                RecommendationPriority.HIGH,
                f"{collaboration_summary['failed_subtasks']} of "
                f"{collaboration_summary['subtask_count']} subtask(s) failed or were cancelled.",
            )
        )

    return recommendations


def _recommendation(
    category: RecommendationCategory, message: str, priority: RecommendationPriority, reason: str
) -> Recommendation:
    return Recommendation(recommendation_id=generate_id(), category=category, message=message, priority=priority, reason=reason)
