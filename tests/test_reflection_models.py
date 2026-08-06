"""Tests for backend.reflection.models: shapes, defaults, and immutability."""

from backend.reflection.models.execution_review import ExecutionReview
from backend.reflection.models.improvement import Improvement
from backend.reflection.models.recommendation import (
    Recommendation,
    RecommendationCategory,
    RecommendationPriority,
)
from backend.reflection.models.reflection_result import ReflectionResult
from backend.reflection.models.reflection_statistics import ReflectionStatistics
from backend.reflection.scoring.confidence_score import ConfidenceScore
from backend.reflection.scoring.efficiency_score import EfficiencyScore
from backend.reflection.scoring.execution_score import ExecutionScore
from backend.utils.time import utc_now


def _score(value: float = 80.0) -> ExecutionScore:
    return ExecutionScore(value=value, breakdown={"status_base": value}, label="good")


def test_recommendation_is_frozen() -> None:
    recommendation = Recommendation(
        recommendation_id="r1",
        category=RecommendationCategory.RETRY,
        message="Retry it.",
        priority=RecommendationPriority.HIGH,
        reason="It failed.",
    )
    try:
        recommendation.message = "changed"  # type: ignore[misc]
        raised = False
    except Exception:  # noqa: BLE001
        raised = True
    assert raised


def test_improvement_shape() -> None:
    improvement = Improvement(
        improvement_id="i1", area="efficiency", description="Low efficiency.", expected_impact="Faster runs."
    )
    assert improvement.area == "efficiency"


def test_execution_review_defaults() -> None:
    review = ExecutionReview(
        overall_success=True,
        execution_score=_score(),
        efficiency_score=EfficiencyScore(value=90.0, breakdown={}, label="excellent"),
        confidence_score=ConfidenceScore(value=70.0, breakdown={}, label="good"),
    )
    assert review.strengths == []
    assert review.weaknesses == []
    assert review.recommendations == []
    assert review.tool_summary == {}
    assert review.future_improvements == []


def test_reflection_result_shape() -> None:
    review = ExecutionReview(
        overall_success=True,
        execution_score=_score(),
        efficiency_score=EfficiencyScore(value=90.0, breakdown={}, label="excellent"),
        confidence_score=ConfidenceScore(value=70.0, breakdown={}, label="good"),
    )
    result = ReflectionResult(
        reflection_id="ref1", plan_id="p1", trace_id="t1", review=review, generated_at=utc_now()
    )
    assert result.session_id is None
    assert result.collaboration_id is None
    assert result.report_id is None


def test_reflection_statistics_defaults() -> None:
    stats = ReflectionStatistics()
    assert stats.total_reflections == 0
    assert stats.by_label == {}
