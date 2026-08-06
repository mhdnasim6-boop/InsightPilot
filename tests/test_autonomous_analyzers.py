"""Tests for backend.autonomous.analyzers: each analyzer is a pure threshold-rule
function over an already-existing statistics model — no AI, no network, no
recomputation of anything the reused service doesn't already aggregate.
"""

from datetime import UTC, datetime

from backend.autonomous.analyzers.distributed_analyzer import DistributedAnalyzer
from backend.autonomous.analyzers.execution_analyzer import ExecutionAnalyzer
from backend.autonomous.analyzers.federation_analyzer import FederationAnalyzer
from backend.autonomous.analyzers.observability_analyzer import ObservabilityAnalyzer
from backend.autonomous.analyzers.resource_analyzer import ResourceAnalyzer
from backend.autonomous.analyzers.workflow_analyzer import WorkflowAnalyzer
from backend.autonomous.models.autonomous_decision import AutonomousVerdict
from backend.autonomous.models.bottleneck import BottleneckCategory, BottleneckSeverity
from backend.distributed.models.cluster_statistics import ClusterStatistics
from backend.federation.models.federation_statistics import FederationStatistics
from backend.federation.models.routing_decision import (
    RoutingDecision,
    RoutingDecisionStatus,
)
from backend.memory.models.memory_statistics import MemoryStatistics
from backend.observability.metrics.models import (
    AIMetrics,
    ExecutionMetricsSummary,
    ToolMetrics,
)
from backend.observability.models.agent_trace import AgentTrace
from backend.observability.models.execution_trace import ExecutionTrace
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.enums import PlanStatus
from backend.reflection.models.reflection_statistics import ReflectionStatistics
from backend.workflows.models.workflow_statistics import WorkflowStatistics

_NOW = datetime.now(UTC)


def _agent_trace(duration_ms: float) -> AgentTrace:
    return AgentTrace(
        agent_name="file_agent", start_time=_NOW, end_time=_NOW, duration_ms=duration_ms,
        status=ExecutionStatus.COMPLETED, input_size=1, output_size=1,
    )


def _trace(duration_ms: float, agent_durations: list[float]) -> ExecutionTrace:
    return ExecutionTrace(
        trace_id="t1", plan_id="p1", start_time=_NOW, duration_ms=duration_ms, status=PlanStatus.COMPLETED,
        agent_traces=[_agent_trace(d) for d in agent_durations],
    )


# -- ExecutionAnalyzer -------------------------------------------------------------------


def test_execution_analyzer_healthy_with_zero_data() -> None:
    bottlenecks, decision = ExecutionAnalyzer().analyze(ExecutionMetricsSummary(), ReflectionStatistics(), 0)
    assert bottlenecks == []
    assert decision.verdict == AutonomousVerdict.HEALTHY
    assert decision.analyzer_name == "ExecutionAnalyzer"


def test_execution_analyzer_flags_critical_execution_time() -> None:
    metrics = ExecutionMetricsSummary(trace_count=5, average_execution_time_ms=150_000.0)
    bottlenecks, decision = ExecutionAnalyzer().analyze(metrics, ReflectionStatistics(), 0)
    assert len(bottlenecks) == 1
    assert bottlenecks[0].category == BottleneckCategory.EXECUTION_EFFICIENCY
    assert bottlenecks[0].severity == BottleneckSeverity.HIGH
    assert decision.verdict == AutonomousVerdict.CRITICAL


def test_execution_analyzer_flags_approval_latency_and_reflection_decline() -> None:
    metrics = ExecutionMetricsSummary(number_of_approvals=3, average_approval_latency_ms=70_000.0)
    reflection = ReflectionStatistics(total_reflections=4, average_execution_score=35.0)
    bottlenecks, decision = ExecutionAnalyzer().analyze(metrics, reflection, 0)
    categories = {b.category for b in bottlenecks}
    assert BottleneckCategory.APPROVAL_BOTTLENECK in categories
    assert BottleneckCategory.REFLECTION_TRENDS in categories
    assert decision.verdict == AutonomousVerdict.CRITICAL


def test_execution_analyzer_flags_recent_failure_count() -> None:
    bottlenecks, _ = ExecutionAnalyzer().analyze(ExecutionMetricsSummary(), ReflectionStatistics(), 5)
    assert len(bottlenecks) == 1
    assert bottlenecks[0].metric_name == "recent_failure_event_count"


# -- WorkflowAnalyzer --------------------------------------------------------------------


def test_workflow_analyzer_healthy_with_zero_data() -> None:
    bottlenecks, decision = WorkflowAnalyzer().analyze(WorkflowStatistics(), [])
    assert bottlenecks == []
    assert decision.verdict == AutonomousVerdict.HEALTHY


def test_workflow_analyzer_flags_critical_duration_and_failure_rate() -> None:
    stats = WorkflowStatistics(total_executions=10, failed_executions=6, average_duration_seconds=400.0)
    bottlenecks, decision = WorkflowAnalyzer().analyze(stats, [])
    categories = [b.category for b in bottlenecks]
    assert BottleneckCategory.WORKFLOW_EFFICIENCY in categories
    assert any(b.severity == BottleneckSeverity.CRITICAL for b in bottlenecks)
    assert decision.verdict == AutonomousVerdict.CRITICAL


def test_workflow_analyzer_flags_low_concurrency_ratio_as_parallelism_opportunity() -> None:
    traces = [_trace(duration_ms=1000.0, agent_durations=[900.0, 90.0])]
    bottlenecks, _ = WorkflowAnalyzer().analyze(WorkflowStatistics(), traces)
    parallelism = [b for b in bottlenecks if b.category == BottleneckCategory.PARALLELISM]
    assert len(parallelism) == 1
    assert parallelism[0].severity == BottleneckSeverity.LOW


def test_workflow_analyzer_ignores_traces_with_no_duration_or_no_agent_traces() -> None:
    traces = [
        ExecutionTrace(trace_id="t2", plan_id="p2", start_time=_NOW, status=PlanStatus.RUNNING),
        _trace(duration_ms=0.0, agent_durations=[100.0]),
    ]
    bottlenecks, _ = WorkflowAnalyzer().analyze(WorkflowStatistics(), traces)
    assert not any(b.category == BottleneckCategory.PARALLELISM for b in bottlenecks)


# -- FederationAnalyzer -------------------------------------------------------------------


def test_federation_analyzer_healthy_with_zero_clusters() -> None:
    bottlenecks, decision = FederationAnalyzer().analyze(FederationStatistics(generated_at=_NOW), [])
    assert bottlenecks == []
    assert decision.verdict == AutonomousVerdict.HEALTHY


def test_federation_analyzer_flags_unavailable_clusters_capacity_and_reroutes() -> None:
    stats = FederationStatistics(
        total_clusters=4, offline_clusters=1, failed_clusters=1, total_capacity=10,
        active_remote_executions=9, generated_at=_NOW,
    )
    decisions = [
        RoutingDecision(
            decision_id="d1", workflow_id="w1", selected_cluster_id="c1", reason="x", decided_at=_NOW,
            status=RoutingDecisionStatus.COMPLETED, reroute_count=1,
        ),
        RoutingDecision(
            decision_id="d2", workflow_id="w2", selected_cluster_id="c1", reason="x", decided_at=_NOW,
            status=RoutingDecisionStatus.COMPLETED,
        ),
    ]
    bottlenecks, decision = FederationAnalyzer().analyze(stats, decisions)
    assert all(b.category == BottleneckCategory.CLUSTER_UTILIZATION for b in bottlenecks)
    assert len(bottlenecks) == 3
    assert decision.verdict == AutonomousVerdict.CRITICAL


# -- DistributedAnalyzer -------------------------------------------------------------------


def test_distributed_analyzer_healthy_with_zero_workers() -> None:
    bottlenecks, decision = DistributedAnalyzer().analyze(ClusterStatistics(generated_at=_NOW))
    assert bottlenecks == []
    assert decision.verdict == AutonomousVerdict.HEALTHY


def test_distributed_analyzer_flags_unavailable_workers_capacity_and_retry_queue() -> None:
    stats = ClusterStatistics(
        total_workers=4, offline_workers=2, failed_workers=1, total_capacity=10, total_active_tasks=9,
        retry_queue_depth=2, generated_at=_NOW,
    )
    bottlenecks, decision = DistributedAnalyzer().analyze(stats)
    assert all(b.category == BottleneckCategory.WORKER_UTILIZATION for b in bottlenecks)
    assert len(bottlenecks) == 3
    assert decision.verdict == AutonomousVerdict.CRITICAL


# -- ObservabilityAnalyzer ------------------------------------------------------------------


def test_observability_analyzer_healthy_with_zero_data() -> None:
    bottlenecks, decision = ObservabilityAnalyzer().analyze([], AIMetrics())
    assert bottlenecks == []
    assert decision.verdict == AutonomousVerdict.HEALTHY


def test_observability_analyzer_flags_tool_failure_rate_and_latency() -> None:
    tool_metrics = [
        ToolMetrics(tool_name="sql_query", call_count=10, failed_count=6, average_duration_ms=15_000.0),
    ]
    bottlenecks, decision = ObservabilityAnalyzer().analyze(tool_metrics, AIMetrics())
    assert len(bottlenecks) == 2
    assert all(b.category == BottleneckCategory.TOOL_USAGE for b in bottlenecks)
    assert all(b.metadata["tool_name"] == "sql_query" for b in bottlenecks)
    assert decision.verdict == AutonomousVerdict.CRITICAL


def test_observability_analyzer_flags_ai_latency() -> None:
    ai_metrics = AIMetrics(call_count=5, average_latency_ms=20_000.0)
    bottlenecks, _ = ObservabilityAnalyzer().analyze([], ai_metrics)
    assert len(bottlenecks) == 1
    assert bottlenecks[0].category == BottleneckCategory.AI_USAGE


# -- ResourceAnalyzer -----------------------------------------------------------------------


def test_resource_analyzer_healthy_with_zero_data() -> None:
    bottlenecks, decision = ResourceAnalyzer().analyze(MemoryStatistics(), 0)
    assert bottlenecks == []
    assert decision.verdict == AutonomousVerdict.HEALTHY


def test_resource_analyzer_flags_memory_volume_low_importance_and_audit_volume() -> None:
    memory = MemoryStatistics(total_items=25_000, average_importance=0.1)
    bottlenecks, decision = ResourceAnalyzer().analyze(memory, 600)
    categories = [b.category for b in bottlenecks]
    assert categories.count(BottleneckCategory.MEMORY_UTILIZATION) == 2
    assert BottleneckCategory.SECURITY_OVERHEAD in categories
    assert decision.verdict == AutonomousVerdict.CRITICAL
