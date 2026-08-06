"""AutonomousService: the single public entry point for autonomous optimization.

Gathers a ``PerformanceProfile`` from every reused service's own
already-computed ``.statistics()``/``.summary()``/``.list_*()`` surface,
runs it through ``BottleneckDetector`` -> the three optimizers ->
``RecommendationEngine`` -> ``SelfHealingEngine``, and stores the
resulting ``OptimizationReport`` in an in-memory, process-wide history
so ``GET /reports``/``GET /reports/{id}`` can look it back up later.

Reuses: ``WorkflowService``, ``AdaptivePlanningService``,
``ObservabilityService`` (+ ``MetricsService``, its own read-side
aggregator), ``ReflectionService``, ``MemoryService``,
``DistributedExecutionService``, ``FederationService``, ``AuditService``
(read-only; see ``resource_analyzer.py``'s own docstring for why this
one extra read-only surface is in scope even though it isn't in this
phase's explicit "Reuse" list). ``ExecutionService`` is deliberately
*not* a constructor dependency here: its own public surface
(``get``/``get_progress``/``get_graph``) is single-execution-oriented
with no fleet-wide aggregate to read, so there is nothing on it this
service could reuse without duplicating that ``ObservabilityService``/
``MetricsService`` don't already aggregate across every execution's own
trace. ``RealtimeService`` is likewise not a dependency of this service:
nothing here needs to observe or replay events to compute a report, and
``backend.realtime.events.event_type.EventType`` is itself in this
phase's own "do not modify" list — this phase's existing
``OPTIMIZATION_GENERATED`` event already belongs to
``AdaptivePlanningService``'s own publisher (Phase 32), so reusing it
here for a differently-shaped payload would misattribute events on the
same realtime stream rather than genuinely reuse anything. A future
phase could add a dedicated event type for this package without
touching any existing one.
"""

from datetime import datetime

from backend.adaptive.services.adaptive_planning_service import AdaptivePlanningService
from backend.autonomous.exceptions import OptimizationReportNotFoundError
from backend.autonomous.healing.self_healing_engine import SelfHealingEngine
from backend.autonomous.models.bottleneck import Bottleneck
from backend.autonomous.models.healing_recommendation import HealingRecommendation
from backend.autonomous.models.optimization_report import OptimizationReport
from backend.autonomous.models.optimization_statistics import OptimizationStatistics
from backend.autonomous.models.performance_profile import PerformanceProfile
from backend.autonomous.optimizer.bottleneck_detector import BottleneckDetector
from backend.autonomous.optimizer.execution_optimizer import ExecutionOptimizer
from backend.autonomous.optimizer.recommendation_engine import RecommendationEngine
from backend.autonomous.optimizer.resource_optimizer import ResourceOptimizer
from backend.autonomous.optimizer.workflow_optimizer import WorkflowOptimizer
from backend.distributed.services.distributed_execution_service import (
    DistributedExecutionService,
)
from backend.federation.services.federation_service import FederationService
from backend.memory.services.memory_service import MemoryService
from backend.observability.metrics.metrics_service import MetricsService
from backend.observability.services.observability_service import ObservabilityService
from backend.planning.models.enums import PlanStatus
from backend.reflection.services.reflection_service import ReflectionService
from backend.security.audit.audit_service import AuditService
from backend.utils.ids import generate_id
from backend.utils.time import utc_now
from backend.workflows.services.workflow_service import WorkflowService


class OptimizationReportStore:
    """The one stateful collaborator in this package: every OptimizationReport ever
    generated, kept in insertion order. Mirrors ``ClusterRegistry``/``WorkerRegistry``'s
    own role in prior phases — the only thing that must survive across requests."""

    def __init__(self) -> None:
        self._reports: dict[str, OptimizationReport] = {}
        self._order: list[str] = []

    def add(self, report: OptimizationReport) -> None:
        self._reports[report.report_id] = report
        self._order.append(report.report_id)

    def get(self, report_id: str) -> OptimizationReport:
        report = self._reports.get(report_id)
        if report is None:
            raise OptimizationReportNotFoundError(f"No optimization report with id '{report_id}'.")
        return report

    def list_all(self) -> list[OptimizationReport]:
        return [self._reports[report_id] for report_id in self._order]


class AutonomousService:
    """The single public entry point for autonomous optimization analysis."""

    def __init__(
        self,
        store: OptimizationReportStore,
        bottleneck_detector: BottleneckDetector,
        execution_optimizer: ExecutionOptimizer,
        workflow_optimizer: WorkflowOptimizer,
        resource_optimizer: ResourceOptimizer,
        recommendation_engine: RecommendationEngine,
        self_healing_engine: SelfHealingEngine,
        workflow_service: WorkflowService,
        adaptive_planning_service: AdaptivePlanningService,
        observability_service: ObservabilityService,
        metrics_service: MetricsService,
        reflection_service: ReflectionService,
        memory_service: MemoryService,
        distributed_execution_service: DistributedExecutionService,
        federation_service: FederationService,
        audit_service: AuditService,
    ) -> None:
        self._store = store
        self._bottleneck_detector = bottleneck_detector
        self._execution_optimizer = execution_optimizer
        self._workflow_optimizer = workflow_optimizer
        self._resource_optimizer = resource_optimizer
        self._recommendation_engine = recommendation_engine
        self._self_healing_engine = self_healing_engine
        self._workflow_service = workflow_service
        self._adaptive_planning_service = adaptive_planning_service
        self._observability_service = observability_service
        self._metrics_service = metrics_service
        self._reflection_service = reflection_service
        self._memory_service = memory_service
        self._distributed_execution_service = distributed_execution_service
        self._federation_service = federation_service
        self._audit_service = audit_service

    def _build_profile(self, now: datetime) -> PerformanceProfile:
        traces = self._observability_service.list_traces()
        recent_failure_event_count = sum(1 for trace in traces if trace.status == PlanStatus.FAILED)
        return PerformanceProfile(
            execution_metrics=self._metrics_service.summary(),
            workflow_statistics=self._workflow_service.statistics(),
            worker_fleet_statistics=self._distributed_execution_service.cluster_statistics(),
            federation_statistics=self._federation_service.federation_statistics(),
            memory_statistics=self._memory_service.statistics(),
            reflection_statistics=self._reflection_service.statistics(),
            adaptive_optimization_statistics=self._adaptive_planning_service.statistics(),
            recent_failure_event_count=recent_failure_event_count,
            audit_event_count=self._audit_service.total_events(),
            generated_at=now,
        )

    def analyze(self) -> OptimizationReport:
        """Run one full analysis pass and store the resulting report."""
        now = utc_now()
        profile = self._build_profile(now)
        traces = self._observability_service.list_traces()
        routing_decisions = self._federation_service.list_routing_decisions()

        bottlenecks, decisions = self._bottleneck_detector.detect(profile, traces, routing_decisions)
        actions = [
            *self._execution_optimizer.generate_actions(bottlenecks),
            *self._workflow_optimizer.generate_actions(bottlenecks),
            *self._resource_optimizer.generate_actions(bottlenecks),
        ]
        bottlenecks_by_id = {bottleneck.bottleneck_id: bottleneck for bottleneck in bottlenecks}
        candidates = self._recommendation_engine.generate(actions, bottlenecks_by_id)
        recommendations = self._self_healing_engine.heal(candidates)

        report = OptimizationReport(
            report_id=generate_id(), performance_profile=profile, decisions=decisions, bottlenecks=bottlenecks,
            actions=actions, recommendations=recommendations, summary=self._summarize(bottlenecks, recommendations),
            generated_at=now,
        )
        self._store.add(report)
        return report

    def _summarize(self, bottlenecks: list[Bottleneck], recommendations: list[HealingRecommendation]) -> str:
        if not bottlenecks:
            return "No bottlenecks detected. The platform is operating within every configured threshold."
        by_category = {bottleneck.category.value for bottleneck in bottlenecks}
        return (
            f"Detected {len(bottlenecks)} bottleneck(s) across {len(by_category)} categor"
            f"{'y' if len(by_category) == 1 else 'ies'}, producing {len(recommendations)} advisory "
            "healing recommendation(s). All recommendations require human review before action."
        )

    def list_reports(self) -> list[OptimizationReport]:
        return self._store.list_all()

    def get_report(self, report_id: str) -> OptimizationReport:
        return self._store.get(report_id)

    def list_recommendations(self) -> list[HealingRecommendation]:
        recommendations: list[HealingRecommendation] = []
        for report in self._store.list_all():
            recommendations.extend(report.recommendations)
        return recommendations

    def statistics(self) -> OptimizationStatistics:
        reports = self._store.list_all()
        by_severity: dict[str, int] = {}
        by_category: dict[str, int] = {}
        total_bottlenecks = 0
        total_actions = 0
        total_recommendations = 0
        last_analyzed_at: datetime | None = None

        for report in reports:
            total_bottlenecks += len(report.bottlenecks)
            total_actions += len(report.actions)
            total_recommendations += len(report.recommendations)
            if last_analyzed_at is None or report.generated_at > last_analyzed_at:
                last_analyzed_at = report.generated_at
            for bottleneck in report.bottlenecks:
                by_severity[bottleneck.severity.value] = by_severity.get(bottleneck.severity.value, 0) + 1
                by_category[bottleneck.category.value] = by_category.get(bottleneck.category.value, 0) + 1

        return OptimizationStatistics(
            total_reports=len(reports), total_bottlenecks=total_bottlenecks, total_actions=total_actions,
            total_recommendations=total_recommendations, by_severity=by_severity, by_category=by_category,
            last_analyzed_at=last_analyzed_at,
        )
