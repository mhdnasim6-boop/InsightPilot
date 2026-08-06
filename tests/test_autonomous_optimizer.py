"""Tests for backend.autonomous.optimizer: BottleneckDetector composes all six
analyzers; the three category-scoped optimizers turn Bottlenecks into advisory
OptimizationActions; RecommendationEngine turns actions into candidate
HealingRecommendations. Every action/recommendation produced here is structurally
advisory-only (``safe_to_automate=False``/``requires_human_approval=True``).
"""

from datetime import UTC, datetime

from backend.autonomous.analyzers.distributed_analyzer import DistributedAnalyzer
from backend.autonomous.analyzers.execution_analyzer import ExecutionAnalyzer
from backend.autonomous.analyzers.federation_analyzer import FederationAnalyzer
from backend.autonomous.analyzers.observability_analyzer import ObservabilityAnalyzer
from backend.autonomous.analyzers.resource_analyzer import ResourceAnalyzer
from backend.autonomous.analyzers.workflow_analyzer import WorkflowAnalyzer
from backend.autonomous.models.bottleneck import (
    Bottleneck,
    BottleneckCategory,
    BottleneckSeverity,
)
from backend.autonomous.models.performance_profile import PerformanceProfile
from backend.autonomous.optimizer.bottleneck_detector import BottleneckDetector
from backend.autonomous.optimizer.execution_optimizer import ExecutionOptimizer
from backend.autonomous.optimizer.recommendation_engine import RecommendationEngine
from backend.autonomous.optimizer.resource_optimizer import ResourceOptimizer
from backend.autonomous.optimizer.workflow_optimizer import WorkflowOptimizer
from backend.distributed.models.cluster_statistics import ClusterStatistics
from backend.federation.models.federation_statistics import FederationStatistics
from backend.utils.ids import generate_id

_NOW = datetime.now(UTC)


def _bottleneck(category: BottleneckCategory, severity: BottleneckSeverity = BottleneckSeverity.MEDIUM) -> Bottleneck:
    return Bottleneck(
        bottleneck_id=generate_id(), category=category, severity=severity, title="t", description="d",
        metric_name="m", metric_value=1.0, threshold=0.5, source="test", detected_at=_NOW,
    )


def _profile() -> PerformanceProfile:
    return PerformanceProfile(
        worker_fleet_statistics=ClusterStatistics(generated_at=_NOW),
        federation_statistics=FederationStatistics(generated_at=_NOW),
        generated_at=_NOW,
    )


def _detector() -> BottleneckDetector:
    return BottleneckDetector(
        execution_analyzer=ExecutionAnalyzer(), workflow_analyzer=WorkflowAnalyzer(),
        federation_analyzer=FederationAnalyzer(), distributed_analyzer=DistributedAnalyzer(),
        observability_analyzer=ObservabilityAnalyzer(), resource_analyzer=ResourceAnalyzer(),
    )


# -- BottleneckDetector -------------------------------------------------------------------


def test_bottleneck_detector_returns_six_decisions_and_no_bottlenecks_with_zero_data() -> None:
    bottlenecks, decisions = _detector().detect(_profile(), [], [])
    assert bottlenecks == []
    assert len(decisions) == 6
    assert {d.analyzer_name for d in decisions} == {
        "ExecutionAnalyzer", "WorkflowAnalyzer", "FederationAnalyzer",
        "DistributedAnalyzer", "ObservabilityAnalyzer", "ResourceAnalyzer",
    }


# -- ExecutionOptimizer / WorkflowOptimizer / ResourceOptimizer ---------------------------


def test_execution_optimizer_only_handles_its_own_categories() -> None:
    bottlenecks = [
        _bottleneck(BottleneckCategory.EXECUTION_EFFICIENCY, BottleneckSeverity.CRITICAL),
        _bottleneck(BottleneckCategory.WORKFLOW_EFFICIENCY),
    ]
    actions = ExecutionOptimizer().generate_actions(bottlenecks)
    assert len(actions) == 1
    assert actions[0].category == BottleneckCategory.EXECUTION_EFFICIENCY
    assert actions[0].estimated_impact == "high"
    assert actions[0].safe_to_automate is False


def test_workflow_optimizer_only_handles_its_own_categories() -> None:
    bottlenecks = [_bottleneck(BottleneckCategory.PARALLELISM, BottleneckSeverity.LOW), _bottleneck(BottleneckCategory.AI_USAGE)]
    actions = WorkflowOptimizer().generate_actions(bottlenecks)
    assert len(actions) == 1
    assert actions[0].category == BottleneckCategory.PARALLELISM
    assert actions[0].estimated_impact == "low"


def test_resource_optimizer_only_handles_its_own_categories() -> None:
    bottlenecks = [
        _bottleneck(BottleneckCategory.MEMORY_UTILIZATION),
        _bottleneck(BottleneckCategory.TOOL_USAGE),
        _bottleneck(BottleneckCategory.SECURITY_OVERHEAD),
        _bottleneck(BottleneckCategory.WORKER_UTILIZATION),
    ]
    actions = ResourceOptimizer().generate_actions(bottlenecks)
    assert {a.category for a in actions} == {
        BottleneckCategory.MEMORY_UTILIZATION, BottleneckCategory.TOOL_USAGE, BottleneckCategory.SECURITY_OVERHEAD,
    }


def test_every_optimizer_action_is_structurally_advisory_only() -> None:
    bottleneck = _bottleneck(BottleneckCategory.EXECUTION_EFFICIENCY)
    for action in ExecutionOptimizer().generate_actions([bottleneck]):
        assert action.safe_to_automate is False


# -- RecommendationEngine -------------------------------------------------------------------


def test_recommendation_engine_derives_risk_from_bottleneck_severity() -> None:
    bottleneck = _bottleneck(BottleneckCategory.EXECUTION_EFFICIENCY, BottleneckSeverity.CRITICAL)
    actions = ExecutionOptimizer().generate_actions([bottleneck])
    recommendations = RecommendationEngine().generate(actions, {bottleneck.bottleneck_id: bottleneck})
    assert len(recommendations) == 1
    assert recommendations[0].risk_level == "high"
    assert recommendations[0].requires_human_approval is True
    assert recommendations[0].bottleneck_id == bottleneck.bottleneck_id
    assert recommendations[0].action_id == actions[0].action_id


def test_recommendation_engine_defaults_to_low_risk_when_bottleneck_missing() -> None:
    bottleneck = _bottleneck(BottleneckCategory.EXECUTION_EFFICIENCY)
    actions = ExecutionOptimizer().generate_actions([bottleneck])
    recommendations = RecommendationEngine().generate(actions, {})
    assert recommendations[0].risk_level == "low"
