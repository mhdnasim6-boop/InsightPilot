"""WorkflowAnalyzer: Workflow efficiency and Parallelism opportunities.

``WorkflowStatistics`` (Phase 36, reused outright via ``WorkflowService.statistics()``)
covers workflow efficiency directly. Parallelism has no existing
aggregate metric anywhere in the codebase, so this analyzer computes one
narrow, honestly-labeled proxy — a "concurrency ratio" — from real
``ExecutionTrace``s already returned by ``ObservabilityService.list_traces()``
(Phase 24, reused): ``sum(agent step durations) / trace wall-clock duration``.
A ratio near 1.0 means steps ran essentially back-to-back (a parallelism
opportunity *if* their dependencies would have allowed overlap — this
analyzer does not inspect the dependency graph itself, so it reports a
proxy signal, not a certainty; see this module's own README section for
the honest caveat).
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
from backend.observability.models.execution_trace import ExecutionTrace
from backend.utils.ids import generate_id
from backend.utils.time import utc_now
from backend.workflows.models.workflow_statistics import WorkflowStatistics

DURATION_WARNING_SECONDS = 60.0
DURATION_CRITICAL_SECONDS = 300.0
FAILURE_RATE_WARNING = 0.2
FAILURE_RATE_CRITICAL = 0.5
CONCURRENCY_RATIO_OPPORTUNITY_THRESHOLD = 1.15


class WorkflowAnalyzer:
    """Detects workflow-duration, failure-rate, and sequential-execution bottlenecks."""

    def analyze(
        self, workflow_statistics: WorkflowStatistics, traces: list[ExecutionTrace],
    ) -> tuple[list[Bottleneck], AutonomousDecision]:
        bottlenecks: list[Bottleneck] = []
        now = utc_now()

        if workflow_statistics.average_duration_seconds >= DURATION_CRITICAL_SECONDS:
            bottlenecks.append(self._bottleneck(
                BottleneckCategory.WORKFLOW_EFFICIENCY, BottleneckSeverity.HIGH,
                "Workflows are taking critically long to complete",
                f"Average workflow duration is {workflow_statistics.average_duration_seconds:.1f}s across "
                f"{workflow_statistics.total_executions} execution(s).",
                "average_duration_seconds", workflow_statistics.average_duration_seconds, DURATION_CRITICAL_SECONDS, now,
            ))
        elif workflow_statistics.average_duration_seconds >= DURATION_WARNING_SECONDS:
            bottlenecks.append(self._bottleneck(
                BottleneckCategory.WORKFLOW_EFFICIENCY, BottleneckSeverity.MEDIUM,
                "Workflow duration is elevated",
                f"Average workflow duration is {workflow_statistics.average_duration_seconds:.1f}s across "
                f"{workflow_statistics.total_executions} execution(s).",
                "average_duration_seconds", workflow_statistics.average_duration_seconds, DURATION_WARNING_SECONDS, now,
            ))

        if workflow_statistics.total_executions > 0:
            failure_rate = workflow_statistics.failed_executions / workflow_statistics.total_executions
            if failure_rate >= FAILURE_RATE_CRITICAL:
                bottlenecks.append(self._bottleneck(
                    BottleneckCategory.WORKFLOW_EFFICIENCY, BottleneckSeverity.CRITICAL,
                    "Most workflow executions are failing",
                    f"{workflow_statistics.failed_executions}/{workflow_statistics.total_executions} execution(s) "
                    f"({failure_rate:.0%}) failed.",
                    "failure_rate", failure_rate, FAILURE_RATE_CRITICAL, now,
                ))
            elif failure_rate >= FAILURE_RATE_WARNING:
                bottlenecks.append(self._bottleneck(
                    BottleneckCategory.WORKFLOW_EFFICIENCY, BottleneckSeverity.MEDIUM,
                    "A significant share of workflow executions are failing",
                    f"{workflow_statistics.failed_executions}/{workflow_statistics.total_executions} execution(s) "
                    f"({failure_rate:.0%}) failed.",
                    "failure_rate", failure_rate, FAILURE_RATE_WARNING, now,
                ))

        ratio = self._average_concurrency_ratio(traces)
        if ratio is not None and ratio <= CONCURRENCY_RATIO_OPPORTUNITY_THRESHOLD:
            bottlenecks.append(self._bottleneck(
                BottleneckCategory.PARALLELISM, BottleneckSeverity.LOW,
                "Steps may be running more sequentially than necessary",
                f"Average concurrency ratio is {ratio:.2f} (near 1.0 means steps ran essentially back-to-back) "
                f"across {len(traces)} trace(s) — a proxy signal, not a dependency-graph guarantee.",
                "concurrency_ratio", ratio, CONCURRENCY_RATIO_OPPORTUNITY_THRESHOLD, now,
            ))

        verdict = self._verdict(bottlenecks)
        decision = AutonomousDecision(
            decision_id=generate_id(), analyzer_name="WorkflowAnalyzer", verdict=verdict,
            bottleneck_ids=[b.bottleneck_id for b in bottlenecks],
            notes=f"{len(bottlenecks)} bottleneck(s) detected across workflow duration/failure/parallelism signals.",
            decided_at=now,
        )
        return bottlenecks, decision

    def _average_concurrency_ratio(self, traces: list[ExecutionTrace]) -> float | None:
        ratios = []
        for trace in traces:
            if not trace.duration_ms or trace.duration_ms <= 0 or not trace.agent_traces:
                continue
            step_total = sum(agent.duration_ms for agent in trace.agent_traces)
            ratios.append(step_total / trace.duration_ms)
        if not ratios:
            return None
        return sum(ratios) / len(ratios)

    def _bottleneck(
        self, category: BottleneckCategory, severity: BottleneckSeverity, title: str, description: str,
        metric_name: str, metric_value: float, threshold: float, now: datetime,
    ) -> Bottleneck:
        return Bottleneck(
            bottleneck_id=generate_id(), category=category, severity=severity, title=title, description=description,
            metric_name=metric_name, metric_value=metric_value, threshold=threshold, source="WorkflowAnalyzer",
            detected_at=now,
        )

    def _verdict(self, bottlenecks: list[Bottleneck]) -> AutonomousVerdict:
        if any(b.severity in {BottleneckSeverity.HIGH, BottleneckSeverity.CRITICAL} for b in bottlenecks):
            return AutonomousVerdict.CRITICAL
        if bottlenecks:
            return AutonomousVerdict.WARNING
        return AutonomousVerdict.HEALTHY
