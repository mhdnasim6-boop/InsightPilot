"""SelfHealingEngine: enrichment and safety validation for candidate recommendations.

The "enrichment and safety validation" half of the recommendation
pipeline — ``backend/autonomous/optimizer/recommendation_engine.py`` is
the "raw generation" half. Takes ``RecommendationEngine``'s own candidate
``HealingRecommendation`` list, replaces each candidate's generic
strategy_name/rationale with the richer, stable text from
``RecoveryStrategyCatalog``, then runs every enriched recommendation
through ``HealingValidator`` — only recommendations that pass are
returned. Never applies, modifies, or automates anything; this package's
entire job ends at producing a validated, human-readable list of advice.
"""

from backend.autonomous.healing.healing_validator import HealingValidator
from backend.autonomous.healing.recovery_strategy import RecoveryStrategyCatalog
from backend.autonomous.models.healing_recommendation import HealingRecommendation


class SelfHealingEngine:
    """Enriches and validates candidate HealingRecommendations before they enter a report."""

    def __init__(self, catalog: RecoveryStrategyCatalog, validator: HealingValidator) -> None:
        self._catalog = catalog
        self._validator = validator

    def heal(self, candidates: list[HealingRecommendation]) -> list[HealingRecommendation]:
        enriched = [
            candidate.model_copy(
                update={
                    "strategy_name": self._catalog.strategy_name_for(candidate.category),
                    "rationale": (
                        f"{self._catalog.rationale_for(candidate.category)} "
                        f"({candidate.rationale})"
                    ),
                }
            )
            for candidate in candidates
        ]
        return self._validator.filter_valid(enriched)
