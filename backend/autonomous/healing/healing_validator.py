"""HealingValidator: the last safety gate before a HealingRecommendation enters a report.

``HealingRecommendation.requires_human_approval`` is already fixed to
``Literal[True]`` at the model level, so no caller can construct an
instance that violates the advisory contract even accidentally. This
validator re-checks that invariant explicitly at runtime anyway — not
because the type system can be wrong, but because a report is a
user-facing artifact and this is the one place in the pipeline whose
entire job is "would I be comfortable this recommendation is safe to
show a human as advice." It also rejects recommendations that are
malformed in ways the type system alone can't express (blank text
fields), so nothing empty or nonsensical reaches the report.
"""

from backend.autonomous.models.healing_recommendation import HealingRecommendation


class HealingValidator:
    """Rejects any candidate recommendation that fails the advisory-only contract."""

    def is_valid(self, recommendation: HealingRecommendation) -> bool:
        return (
            recommendation.requires_human_approval is True
            and bool(recommendation.strategy_name.strip())
            and bool(recommendation.title.strip())
            and bool(recommendation.description.strip())
            and bool(recommendation.rationale.strip())
            and bool(recommendation.bottleneck_id.strip())
        )

    def filter_valid(self, recommendations: list[HealingRecommendation]) -> list[HealingRecommendation]:
        return [r for r in recommendations if self.is_valid(r)]
