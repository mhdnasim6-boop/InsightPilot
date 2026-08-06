"""Tests for backend.autonomous.models: every model is frozen, and the advisory-only
contract (``OptimizationAction.safe_to_automate``/``HealingRecommendation.requires_human_approval``)
is enforced structurally, not just by convention — a caller cannot construct a violating
instance even by trying.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.autonomous.models.bottleneck import (
    Bottleneck,
    BottleneckCategory,
    BottleneckSeverity,
)
from backend.autonomous.models.healing_recommendation import HealingRecommendation
from backend.autonomous.models.optimization_action import OptimizationAction
from backend.autonomous.models.optimization_statistics import OptimizationStatistics
from backend.autonomous.models.performance_profile import PerformanceProfile
from backend.distributed.models.cluster_statistics import ClusterStatistics
from backend.federation.models.federation_statistics import FederationStatistics

_NOW = datetime.now(UTC)


def _action(**overrides: object) -> OptimizationAction:
    fields: dict[str, object] = {
        "action_id": "a1", "bottleneck_id": "b1", "category": BottleneckCategory.EXECUTION_EFFICIENCY,
        "title": "t", "description": "d", "estimated_impact": "low", "created_at": _NOW,
    }
    fields.update(overrides)
    return OptimizationAction(**fields)  # type: ignore[arg-type]


def _recommendation(**overrides: object) -> HealingRecommendation:
    fields: dict[str, object] = {
        "recommendation_id": "r1", "bottleneck_id": "b1", "category": BottleneckCategory.EXECUTION_EFFICIENCY,
        "strategy_name": "s", "title": "t", "description": "d", "rationale": "r", "risk_level": "low",
        "created_at": _NOW,
    }
    fields.update(overrides)
    return HealingRecommendation(**fields)  # type: ignore[arg-type]


def test_optimization_action_safe_to_automate_defaults_false() -> None:
    assert _action().safe_to_automate is False


def test_optimization_action_rejects_an_attempt_to_flip_safe_to_automate() -> None:
    with pytest.raises(ValidationError):
        _action(safe_to_automate=True)


def test_healing_recommendation_requires_human_approval_defaults_true() -> None:
    assert _recommendation().requires_human_approval is True


def test_healing_recommendation_rejects_an_attempt_to_flip_requires_human_approval() -> None:
    with pytest.raises(ValidationError):
        _recommendation(requires_human_approval=False)


def test_bottleneck_is_frozen() -> None:
    bottleneck = Bottleneck(
        bottleneck_id="b1", category=BottleneckCategory.EXECUTION_EFFICIENCY, severity=BottleneckSeverity.LOW,
        title="t", description="d", metric_name="m", metric_value=1.0, threshold=0.5, source="s", detected_at=_NOW,
    )
    with pytest.raises(ValidationError):
        bottleneck.title = "changed"  # type: ignore[misc]


def test_performance_profile_defaults_are_zero_data_safe() -> None:
    profile = PerformanceProfile(
        worker_fleet_statistics=ClusterStatistics(generated_at=_NOW),
        federation_statistics=FederationStatistics(generated_at=_NOW), generated_at=_NOW,
    )
    assert profile.execution_metrics.trace_count == 0
    assert profile.workflow_statistics.total_workflows == 0
    assert profile.memory_statistics.total_items == 0
    assert profile.reflection_statistics.total_reflections == 0
    assert profile.adaptive_optimization_statistics.total_optimizations == 0


def test_optimization_statistics_defaults_are_zero_data_safe() -> None:
    stats = OptimizationStatistics()
    assert stats.total_reports == 0
    assert stats.by_severity == {}
    assert stats.by_category == {}
    assert stats.last_analyzed_at is None
