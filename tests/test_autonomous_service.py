"""Tests for backend.autonomous.services.autonomous_service: OptimizationReportStore's
own get/list semantics, and AutonomousService's own report-history read surface
(statistics aggregation, recommendation flattening, not-found handling) — seeded
directly with hand-built OptimizationReports, independent of the real reused-service
stack (that full, real chain is exercised end-to-end by
``tests/test_autonomous_dependencies.py``/``tests/test_api_v1_autonomous.py``/
``tests/test_autonomous_integration.py``).
"""

from datetime import UTC, datetime, timedelta

import pytest

from backend.autonomous.exceptions import OptimizationReportNotFoundError
from backend.autonomous.models.autonomous_decision import (
    AutonomousDecision,
    AutonomousVerdict,
)
from backend.autonomous.models.bottleneck import (
    Bottleneck,
    BottleneckCategory,
    BottleneckSeverity,
)
from backend.autonomous.models.healing_recommendation import HealingRecommendation
from backend.autonomous.models.optimization_action import OptimizationAction
from backend.autonomous.models.optimization_report import OptimizationReport
from backend.autonomous.models.performance_profile import PerformanceProfile
from backend.autonomous.services.autonomous_service import (
    AutonomousService,
    OptimizationReportStore,
)
from backend.distributed.models.cluster_statistics import ClusterStatistics
from backend.federation.models.federation_statistics import FederationStatistics
from backend.utils.ids import generate_id

_NOW = datetime.now(UTC)


def _profile(now: datetime) -> PerformanceProfile:
    return PerformanceProfile(
        worker_fleet_statistics=ClusterStatistics(generated_at=now),
        federation_statistics=FederationStatistics(generated_at=now), generated_at=now,
    )


def _report(now: datetime, severity: BottleneckSeverity, category: BottleneckCategory) -> OptimizationReport:
    bottleneck = Bottleneck(
        bottleneck_id=generate_id(), category=category, severity=severity, title="t", description="d",
        metric_name="m", metric_value=1.0, threshold=0.5, source="s", detected_at=now,
    )
    action = OptimizationAction(
        action_id=generate_id(), bottleneck_id=bottleneck.bottleneck_id, category=category, title="t",
        description="d", estimated_impact="low", created_at=now,
    )
    recommendation = HealingRecommendation(
        recommendation_id=generate_id(), bottleneck_id=bottleneck.bottleneck_id, action_id=action.action_id,
        category=category, strategy_name="s", title="t", description="d", rationale="r", risk_level="low",
        created_at=now,
    )
    decision = AutonomousDecision(
        decision_id=generate_id(), analyzer_name="TestAnalyzer", verdict=AutonomousVerdict.WARNING,
        bottleneck_ids=[bottleneck.bottleneck_id], decided_at=now,
    )
    return OptimizationReport(
        report_id=generate_id(), performance_profile=_profile(now), decisions=[decision], bottlenecks=[bottleneck],
        actions=[action], recommendations=[recommendation], generated_at=now,
    )


def _service(store: OptimizationReportStore) -> AutonomousService:
    return AutonomousService(
        store=store, bottleneck_detector=None, execution_optimizer=None, workflow_optimizer=None,  # type: ignore[arg-type]
        resource_optimizer=None, recommendation_engine=None, self_healing_engine=None,  # type: ignore[arg-type]
        workflow_service=None, adaptive_planning_service=None, observability_service=None,  # type: ignore[arg-type]
        metrics_service=None, reflection_service=None, memory_service=None,  # type: ignore[arg-type]
        distributed_execution_service=None, federation_service=None, audit_service=None,  # type: ignore[arg-type]
    )


# -- OptimizationReportStore ------------------------------------------------------------


def test_store_get_raises_for_unknown_report_id() -> None:
    with pytest.raises(OptimizationReportNotFoundError):
        OptimizationReportStore().get("does-not-exist")


def test_store_list_all_preserves_insertion_order() -> None:
    store = OptimizationReportStore()
    first = _report(_NOW, BottleneckSeverity.LOW, BottleneckCategory.MEMORY_UTILIZATION)
    second = _report(_NOW + timedelta(seconds=1), BottleneckSeverity.HIGH, BottleneckCategory.TOOL_USAGE)
    store.add(first)
    store.add(second)
    assert [r.report_id for r in store.list_all()] == [first.report_id, second.report_id]


# -- AutonomousService read surface ------------------------------------------------------


def test_get_report_raises_optimization_report_not_found_error() -> None:
    service = _service(OptimizationReportStore())
    with pytest.raises(OptimizationReportNotFoundError):
        service.get_report("does-not-exist")


def test_statistics_aggregates_across_every_stored_report() -> None:
    store = OptimizationReportStore()
    store.add(_report(_NOW, BottleneckSeverity.LOW, BottleneckCategory.MEMORY_UTILIZATION))
    later = _NOW + timedelta(seconds=1)
    store.add(_report(later, BottleneckSeverity.HIGH, BottleneckCategory.TOOL_USAGE))
    stats = _service(store).statistics()

    assert stats.total_reports == 2
    assert stats.total_bottlenecks == 2
    assert stats.total_actions == 2
    assert stats.total_recommendations == 2
    assert stats.by_severity == {"low": 1, "high": 1}
    assert stats.by_category == {"memory_utilization": 1, "tool_usage": 1}
    assert stats.last_analyzed_at == later


def test_statistics_on_empty_store_matches_zero_data_defaults() -> None:
    stats = _service(OptimizationReportStore()).statistics()
    assert stats.total_reports == 0
    assert stats.by_severity == {}
    assert stats.last_analyzed_at is None


def test_list_recommendations_flattens_across_every_report() -> None:
    store = OptimizationReportStore()
    report_a = _report(_NOW, BottleneckSeverity.LOW, BottleneckCategory.MEMORY_UTILIZATION)
    report_b = _report(_NOW, BottleneckSeverity.HIGH, BottleneckCategory.TOOL_USAGE)
    store.add(report_a)
    store.add(report_b)
    recommendations = _service(store).list_recommendations()
    assert {r.recommendation_id for r in recommendations} == {
        report_a.recommendations[0].recommendation_id, report_b.recommendations[0].recommendation_id,
    }
