"""BottleneckDetector: runs every analyzer over one PerformanceProfile.

The single place that composes all six analyzers — ``AutonomousService``
itself never calls an analyzer directly, so adding a future seventh
analyzer only ever touches this one class.
"""

from backend.autonomous.analyzers.distributed_analyzer import DistributedAnalyzer
from backend.autonomous.analyzers.execution_analyzer import ExecutionAnalyzer
from backend.autonomous.analyzers.federation_analyzer import FederationAnalyzer
from backend.autonomous.analyzers.observability_analyzer import ObservabilityAnalyzer
from backend.autonomous.analyzers.resource_analyzer import ResourceAnalyzer
from backend.autonomous.analyzers.workflow_analyzer import WorkflowAnalyzer
from backend.autonomous.models.autonomous_decision import AutonomousDecision
from backend.autonomous.models.bottleneck import Bottleneck
from backend.autonomous.models.performance_profile import PerformanceProfile
from backend.federation.models.routing_decision import RoutingDecision
from backend.observability.models.execution_trace import ExecutionTrace


class BottleneckDetector:
    """Runs every analyzer over one PerformanceProfile and collects every finding."""

    def __init__(
        self,
        execution_analyzer: ExecutionAnalyzer,
        workflow_analyzer: WorkflowAnalyzer,
        federation_analyzer: FederationAnalyzer,
        distributed_analyzer: DistributedAnalyzer,
        observability_analyzer: ObservabilityAnalyzer,
        resource_analyzer: ResourceAnalyzer,
    ) -> None:
        self._execution_analyzer = execution_analyzer
        self._workflow_analyzer = workflow_analyzer
        self._federation_analyzer = federation_analyzer
        self._distributed_analyzer = distributed_analyzer
        self._observability_analyzer = observability_analyzer
        self._resource_analyzer = resource_analyzer

    def detect(
        self, profile: PerformanceProfile, traces: list[ExecutionTrace], routing_decisions: list[RoutingDecision],
    ) -> tuple[list[Bottleneck], list[AutonomousDecision]]:
        """Run every analyzer and return every Bottleneck + AutonomousDecision produced."""
        bottlenecks: list[Bottleneck] = []
        decisions: list[AutonomousDecision] = []

        for analyzer_bottlenecks, decision in (
            self._execution_analyzer.analyze(
                profile.execution_metrics, profile.reflection_statistics, profile.recent_failure_event_count,
            ),
            self._workflow_analyzer.analyze(profile.workflow_statistics, traces),
            self._federation_analyzer.analyze(profile.federation_statistics, routing_decisions),
            self._distributed_analyzer.analyze(profile.worker_fleet_statistics),
            self._observability_analyzer.analyze(profile.execution_metrics.tool_metrics, profile.execution_metrics.ai_metrics),
            self._resource_analyzer.analyze(profile.memory_statistics, profile.audit_event_count),
        ):
            bottlenecks.extend(analyzer_bottlenecks)
            decisions.append(decision)

        return bottlenecks, decisions
