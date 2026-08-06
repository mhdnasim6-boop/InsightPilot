"""RecommendationEngine: turns OptimizationActions into candidate HealingRecommendations.

The "raw generation" half of the recommendation pipeline —
``backend/autonomous/healing/self_healing_engine.py`` is the
"enrichment and safety validation" half (cross-referencing the
``RecoveryStrategy`` catalog and running every candidate through
``HealingValidator`` before it's allowed into a report). ``risk_level``
here means *risk of leaving the underlying Bottleneck unaddressed*, not
risk of the recommendation itself — every recommendation this package
can produce is advisory-only and inherently zero-risk to apply, since
nothing here ever applies anything.
"""

from typing import Literal

from backend.autonomous.models.bottleneck import Bottleneck, BottleneckSeverity
from backend.autonomous.models.healing_recommendation import HealingRecommendation
from backend.autonomous.models.optimization_action import OptimizationAction
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

_RISK_BY_SEVERITY: dict[BottleneckSeverity, Literal["low", "medium", "high"]] = {
    BottleneckSeverity.LOW: "low",
    BottleneckSeverity.MEDIUM: "low",
    BottleneckSeverity.HIGH: "medium",
    BottleneckSeverity.CRITICAL: "high",
}


class RecommendationEngine:
    """Turns OptimizationActions into candidate, advisory HealingRecommendations."""

    def generate(self, actions: list[OptimizationAction], bottlenecks: dict[str, Bottleneck]) -> list[HealingRecommendation]:
        recommendations = []
        for action in actions:
            bottleneck = bottlenecks.get(action.bottleneck_id)
            severity = bottleneck.severity if bottleneck is not None else BottleneckSeverity.LOW
            recommendations.append(
                HealingRecommendation(
                    recommendation_id=generate_id(), bottleneck_id=action.bottleneck_id, action_id=action.action_id,
                    category=action.category, strategy_name=f"review_{action.category.value}",
                    title=action.title, description=action.description,
                    rationale=(
                        f"Leaving '{action.title}' unaddressed carries {_RISK_BY_SEVERITY[severity]} risk of "
                        "continued or worsening impact, based on the detected bottleneck's own severity."
                    ),
                    risk_level=_RISK_BY_SEVERITY[severity], created_at=utc_now(),
                )
            )
        return recommendations
