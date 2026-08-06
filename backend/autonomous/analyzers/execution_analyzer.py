"""ExecutionAnalyzer: Execution efficiency, Approval bottlenecks, and Reflection trends.

Three categories share one analyzer because they share one natural data
source per category: ``MetricsService.summary()`` (Phase 24, reused
outright — never recomputed from raw traces) already aggregates both
execution timing *and* approval latency across every known
``ExecutionTrace``; ``ReflectionService.statistics()`` (Phase 31, reused
outright) already aggregates score trends across every stored
reflection. A supplementary signal — ``RealtimeService.replay()`` (Phase
37) filtered to ``*_failed`` event types — adds *recency* (how many
failures happened just now) that a lifetime-aggregate metric alone can't
show.
"""

from datetime import datetime

from backend.autonomous.models.autonomous_decision import (
    AutonomousDecision,
    AutonomousVerdict,
)
from backend.autonomous.models.bottleneck import (
    Bottleneck,
    BottleneckCategory,
    BottleneckSeverity,
)
from backend.observability.metrics.models import ExecutionMetricsSummary
from backend.reflection.models.reflection_statistics import ReflectionStatistics
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

EXECUTION_TIME_WARNING_MS = 30_000.0
EXECUTION_TIME_CRITICAL_MS = 120_000.0
APPROVAL_LATENCY_WARNING_MS = 60_000.0
APPROVAL_LATENCY_CRITICAL_MS = 300_000.0
REFLECTION_SCORE_WARNING = 60.0
REFLECTION_SCORE_CRITICAL = 40.0
RECENT_FAILURE_WARNING_COUNT = 5


class ExecutionAnalyzer:
    """Detects execution-timing, approval-latency, and reflection-quality bottlenecks."""

    def analyze(
        self, execution_metrics: ExecutionMetricsSummary, reflection_statistics: ReflectionStatistics,
        recent_failure_event_count: int,
    ) -> tuple[list[Bottleneck], AutonomousDecision]:
        bottlenecks: list[Bottleneck] = []
        now = utc_now()

        if execution_metrics.trace_count > 0:
            if execution_metrics.average_execution_time_ms >= EXECUTION_TIME_CRITICAL_MS:
                bottlenecks.append(self._bottleneck(
                    BottleneckCategory.EXECUTION_EFFICIENCY, BottleneckSeverity.HIGH,
                    "Execution time is critically high",
                    f"Average execution time is {execution_metrics.average_execution_time_ms:.0f}ms across "
                    f"{execution_metrics.trace_count} trace(s).",
                    "average_execution_time_ms", execution_metrics.average_execution_time_ms, EXECUTION_TIME_CRITICAL_MS, now,
                ))
            elif execution_metrics.average_execution_time_ms >= EXECUTION_TIME_WARNING_MS:
                bottlenecks.append(self._bottleneck(
                    BottleneckCategory.EXECUTION_EFFICIENCY, BottleneckSeverity.MEDIUM,
                    "Execution time is elevated",
                    f"Average execution time is {execution_metrics.average_execution_time_ms:.0f}ms across "
                    f"{execution_metrics.trace_count} trace(s).",
                    "average_execution_time_ms", execution_metrics.average_execution_time_ms, EXECUTION_TIME_WARNING_MS, now,
                ))

        if execution_metrics.number_of_approvals > 0:
            if execution_metrics.average_approval_latency_ms >= APPROVAL_LATENCY_CRITICAL_MS:
                bottlenecks.append(self._bottleneck(
                    BottleneckCategory.APPROVAL_BOTTLENECK, BottleneckSeverity.HIGH,
                    "Approvals are taking very long to decide",
                    f"Average approval latency is {execution_metrics.average_approval_latency_ms:.0f}ms across "
                    f"{execution_metrics.number_of_approvals} approval(s).",
                    "average_approval_latency_ms", execution_metrics.average_approval_latency_ms,
                    APPROVAL_LATENCY_CRITICAL_MS, now,
                ))
            elif execution_metrics.average_approval_latency_ms >= APPROVAL_LATENCY_WARNING_MS:
                bottlenecks.append(self._bottleneck(
                    BottleneckCategory.APPROVAL_BOTTLENECK, BottleneckSeverity.MEDIUM,
                    "Approvals are slower than expected",
                    f"Average approval latency is {execution_metrics.average_approval_latency_ms:.0f}ms across "
                    f"{execution_metrics.number_of_approvals} approval(s).",
                    "average_approval_latency_ms", execution_metrics.average_approval_latency_ms,
                    APPROVAL_LATENCY_WARNING_MS, now,
                ))

        if reflection_statistics.total_reflections > 0:
            if reflection_statistics.average_execution_score <= REFLECTION_SCORE_CRITICAL:
                bottlenecks.append(self._bottleneck(
                    BottleneckCategory.REFLECTION_TRENDS, BottleneckSeverity.HIGH,
                    "Reflections show consistently poor execution quality",
                    f"Average execution score is {reflection_statistics.average_execution_score:.1f}/100 across "
                    f"{reflection_statistics.total_reflections} reflection(s).",
                    "average_execution_score", reflection_statistics.average_execution_score, REFLECTION_SCORE_CRITICAL, now,
                ))
            elif reflection_statistics.average_execution_score <= REFLECTION_SCORE_WARNING:
                bottlenecks.append(self._bottleneck(
                    BottleneckCategory.REFLECTION_TRENDS, BottleneckSeverity.MEDIUM,
                    "Reflections show declining execution quality",
                    f"Average execution score is {reflection_statistics.average_execution_score:.1f}/100 across "
                    f"{reflection_statistics.total_reflections} reflection(s).",
                    "average_execution_score", reflection_statistics.average_execution_score, REFLECTION_SCORE_WARNING, now,
                ))

        if recent_failure_event_count >= RECENT_FAILURE_WARNING_COUNT:
            bottlenecks.append(self._bottleneck(
                BottleneckCategory.EXECUTION_EFFICIENCY, BottleneckSeverity.MEDIUM,
                "Elevated failure activity in the live event stream",
                f"{recent_failure_event_count} failure event(s) observed in the recent realtime replay window.",
                "recent_failure_event_count", float(recent_failure_event_count), float(RECENT_FAILURE_WARNING_COUNT), now,
            ))

        verdict = self._verdict(bottlenecks)
        decision = AutonomousDecision(
            decision_id=generate_id(), analyzer_name="ExecutionAnalyzer", verdict=verdict,
            bottleneck_ids=[b.bottleneck_id for b in bottlenecks],
            notes=f"{len(bottlenecks)} bottleneck(s) detected across execution/approval/reflection signals.",
            decided_at=now,
        )
        return bottlenecks, decision

    def _bottleneck(
        self, category: BottleneckCategory, severity: BottleneckSeverity, title: str, description: str,
        metric_name: str, metric_value: float, threshold: float, now: datetime,
    ) -> Bottleneck:
        return Bottleneck(
            bottleneck_id=generate_id(), category=category, severity=severity, title=title, description=description,
            metric_name=metric_name, metric_value=metric_value, threshold=threshold, source="ExecutionAnalyzer",
            detected_at=now,
        )

    def _verdict(self, bottlenecks: list[Bottleneck]) -> AutonomousVerdict:
        if any(b.severity in {BottleneckSeverity.HIGH, BottleneckSeverity.CRITICAL} for b in bottlenecks):
            return AutonomousVerdict.CRITICAL
        if bottlenecks:
            return AutonomousVerdict.WARNING
        return AutonomousVerdict.HEALTHY
