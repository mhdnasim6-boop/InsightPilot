"""Tests for backend.autonomous.exporters: JSON/Markdown/Mermaid rendering of a complete
OptimizationReport — pure formatting, nothing computed here.
"""

import json
from datetime import UTC, datetime

from backend.autonomous.exporters.json_exporter import export_optimization_report_json
from backend.autonomous.exporters.markdown_exporter import (
    export_optimization_report_markdown,
)
from backend.autonomous.exporters.mermaid_exporter import (
    export_optimization_report_mermaid,
)
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
from backend.distributed.models.cluster_statistics import ClusterStatistics
from backend.federation.models.federation_statistics import FederationStatistics
from backend.utils.ids import generate_id

_NOW = datetime.now(UTC)


def _report() -> OptimizationReport:
    bottleneck = Bottleneck(
        bottleneck_id="b1", category=BottleneckCategory.EXECUTION_EFFICIENCY, severity=BottleneckSeverity.HIGH,
        title="Slow executions", description="d", metric_name="average_execution_time_ms", metric_value=150_000.0,
        threshold=120_000.0, source="ExecutionAnalyzer", detected_at=_NOW,
    )
    action = OptimizationAction(
        action_id="a1", bottleneck_id="b1", category=BottleneckCategory.EXECUTION_EFFICIENCY,
        title="Address: Slow executions", description="Review timing.", estimated_impact="high", created_at=_NOW,
    )
    recommendation = HealingRecommendation(
        recommendation_id="r1", bottleneck_id="b1", action_id="a1", category=BottleneckCategory.EXECUTION_EFFICIENCY,
        strategy_name="review_execution_timing", title="Address: Slow executions", description="Review timing.",
        rationale="Risk of inaction.", risk_level="high", created_at=_NOW,
    )
    decision = AutonomousDecision(
        decision_id="d1", analyzer_name="ExecutionAnalyzer", verdict=AutonomousVerdict.CRITICAL,
        bottleneck_ids=["b1"], notes="1 bottleneck detected.", decided_at=_NOW,
    )
    profile = PerformanceProfile(
        worker_fleet_statistics=ClusterStatistics(generated_at=_NOW),
        federation_statistics=FederationStatistics(generated_at=_NOW), generated_at=_NOW,
    )
    return OptimizationReport(
        report_id=generate_id(), performance_profile=profile, decisions=[decision], bottlenecks=[bottleneck],
        actions=[action], recommendations=[recommendation], summary="1 bottleneck detected.", generated_at=_NOW,
    )


def test_json_exporter_round_trips_every_top_level_field() -> None:
    payload = json.loads(export_optimization_report_json(_report()))
    assert payload["report_id"]
    assert len(payload["bottlenecks"]) == 1
    assert len(payload["actions"]) == 1
    assert len(payload["recommendations"]) == 1
    assert len(payload["decisions"]) == 1


def test_markdown_exporter_includes_every_section() -> None:
    markdown = export_optimization_report_markdown(_report())
    assert "# Optimization Report" in markdown
    assert "## Decisions" in markdown
    assert "## Bottlenecks" in markdown
    assert "## Suggested Actions" in markdown
    assert "## Healing Recommendations (advisory only)" in markdown
    assert "Slow executions" in markdown


def test_mermaid_exporter_chains_bottleneck_to_action_to_recommendation() -> None:
    mermaid = export_optimization_report_mermaid(_report())
    assert mermaid.startswith("flowchart LR")
    assert "b1 --> a1" in mermaid
    assert "a1 --> r1" in mermaid
