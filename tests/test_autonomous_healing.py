"""Tests for backend.autonomous.healing: RecoveryStrategyCatalog's stable name/rationale
lookup, HealingValidator's advisory-contract safety gate, and SelfHealingEngine's own
enrich-then-validate pipeline over RecommendationEngine's candidate output.
"""

from datetime import UTC, datetime

from backend.autonomous.healing.healing_validator import HealingValidator
from backend.autonomous.healing.recovery_strategy import RecoveryStrategyCatalog
from backend.autonomous.healing.self_healing_engine import SelfHealingEngine
from backend.autonomous.models.bottleneck import BottleneckCategory
from backend.autonomous.models.healing_recommendation import HealingRecommendation

_NOW = datetime.now(UTC)


def _recommendation(**overrides: object) -> HealingRecommendation:
    fields: dict[str, object] = {
        "recommendation_id": "r1", "bottleneck_id": "b1", "action_id": "a1",
        "category": BottleneckCategory.EXECUTION_EFFICIENCY, "strategy_name": "review_execution_efficiency",
        "title": "Address it", "description": "Do something.", "rationale": "Because.", "risk_level": "medium",
        "created_at": _NOW,
    }
    fields.update(overrides)
    return HealingRecommendation(**fields)  # type: ignore[arg-type]


# -- RecoveryStrategyCatalog ----------------------------------------------------------------


def test_recovery_strategy_catalog_returns_a_stable_name_and_rationale_for_every_category() -> None:
    catalog = RecoveryStrategyCatalog()
    for category in BottleneckCategory:
        name = catalog.strategy_name_for(category)
        rationale = catalog.rationale_for(category)
        assert name
        assert rationale


# -- HealingValidator -------------------------------------------------------------------------


def test_healing_validator_accepts_a_well_formed_recommendation() -> None:
    assert HealingValidator().is_valid(_recommendation()) is True


def test_healing_validator_rejects_blank_text_fields() -> None:
    validator = HealingValidator()
    assert validator.is_valid(_recommendation(strategy_name="")) is False
    assert validator.is_valid(_recommendation(title="  ")) is False
    assert validator.is_valid(_recommendation(rationale="")) is False


def test_healing_validator_filter_valid_drops_only_invalid_entries() -> None:
    good = _recommendation(recommendation_id="good")
    bad = _recommendation(recommendation_id="bad", description="")
    filtered = HealingValidator().filter_valid([good, bad])
    assert filtered == [good]


# -- SelfHealingEngine ------------------------------------------------------------------------


def test_self_healing_engine_enriches_strategy_name_and_rationale() -> None:
    engine = SelfHealingEngine(RecoveryStrategyCatalog(), HealingValidator())
    candidate = _recommendation(strategy_name="review_execution_efficiency", rationale="raw rationale")
    healed = engine.heal([candidate])
    assert len(healed) == 1
    assert healed[0].strategy_name == "review_execution_timing"
    assert "raw rationale" in healed[0].rationale
    assert healed[0].requires_human_approval is True


def test_self_healing_engine_drops_candidates_that_fail_validation() -> None:
    engine = SelfHealingEngine(RecoveryStrategyCatalog(), HealingValidator())
    candidate = _recommendation(title="")
    assert engine.heal([candidate]) == []
