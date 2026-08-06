"""DistributedAnalyzer: Worker utilization.

Reuses ``DistributedExecutionService.cluster_statistics()`` (Phase 38)
outright — never a raw recomputation from ``WorkerRegistry``/``TaskQueue``
directly.
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
from backend.distributed.models.cluster_statistics import ClusterStatistics
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

UNAVAILABLE_WORKER_RATIO_WARNING = 0.25
UNAVAILABLE_WORKER_RATIO_CRITICAL = 0.5
CAPACITY_UTILIZATION_WARNING = 0.8
RETRY_QUEUE_WARNING_DEPTH = 1


class DistributedAnalyzer:
    """Detects worker-availability, worker-capacity, and recovery-activity bottlenecks."""

    def analyze(self, worker_fleet_statistics: ClusterStatistics) -> tuple[list[Bottleneck], AutonomousDecision]:
        bottlenecks: list[Bottleneck] = []
        now = utc_now()

        if worker_fleet_statistics.total_workers > 0:
            unavailable = worker_fleet_statistics.offline_workers + worker_fleet_statistics.failed_workers
            ratio = unavailable / worker_fleet_statistics.total_workers
            if ratio >= UNAVAILABLE_WORKER_RATIO_CRITICAL:
                bottlenecks.append(self._bottleneck(
                    BottleneckSeverity.CRITICAL, "Most workers are unavailable",
                    f"{unavailable}/{worker_fleet_statistics.total_workers} worker(s) ({ratio:.0%}) are OFFLINE/FAILED.",
                    "unavailable_worker_ratio", ratio, UNAVAILABLE_WORKER_RATIO_CRITICAL, now,
                ))
            elif ratio >= UNAVAILABLE_WORKER_RATIO_WARNING:
                bottlenecks.append(self._bottleneck(
                    BottleneckSeverity.MEDIUM, "A significant share of workers are unavailable",
                    f"{unavailable}/{worker_fleet_statistics.total_workers} worker(s) ({ratio:.0%}) are OFFLINE/FAILED.",
                    "unavailable_worker_ratio", ratio, UNAVAILABLE_WORKER_RATIO_WARNING, now,
                ))

        if worker_fleet_statistics.total_capacity > 0:
            utilization = worker_fleet_statistics.total_active_tasks / worker_fleet_statistics.total_capacity
            if utilization >= CAPACITY_UTILIZATION_WARNING:
                bottlenecks.append(self._bottleneck(
                    BottleneckSeverity.MEDIUM, "Worker fleet capacity is nearly exhausted",
                    f"{worker_fleet_statistics.total_active_tasks}/{worker_fleet_statistics.total_capacity} "
                    f"({utilization:.0%}) of worker capacity is in use.",
                    "capacity_utilization", utilization, CAPACITY_UTILIZATION_WARNING, now,
                ))

        if worker_fleet_statistics.retry_queue_depth >= RETRY_QUEUE_WARNING_DEPTH:
            bottlenecks.append(self._bottleneck(
                BottleneckSeverity.MEDIUM, "Tasks are awaiting retry after a lost worker/lease",
                f"{worker_fleet_statistics.retry_queue_depth} task(s) are currently in the retry queue.",
                "retry_queue_depth", float(worker_fleet_statistics.retry_queue_depth), float(RETRY_QUEUE_WARNING_DEPTH), now,
            ))

        verdict = self._verdict(bottlenecks)
        decision = AutonomousDecision(
            decision_id=generate_id(), analyzer_name="DistributedAnalyzer", verdict=verdict,
            bottleneck_ids=[b.bottleneck_id for b in bottlenecks],
            notes=f"{len(bottlenecks)} bottleneck(s) detected across worker availability/capacity/recovery signals.",
            decided_at=now,
        )
        return bottlenecks, decision

    def _bottleneck(
        self, severity: BottleneckSeverity, title: str, description: str,
        metric_name: str, metric_value: float, threshold: float, now: datetime,
    ) -> Bottleneck:
        return Bottleneck(
            bottleneck_id=generate_id(), category=BottleneckCategory.WORKER_UTILIZATION, severity=severity,
            title=title, description=description, metric_name=metric_name, metric_value=metric_value,
            threshold=threshold, source="DistributedAnalyzer", detected_at=now,
        )

    def _verdict(self, bottlenecks: list[Bottleneck]) -> AutonomousVerdict:
        if any(b.severity in {BottleneckSeverity.HIGH, BottleneckSeverity.CRITICAL} for b in bottlenecks):
            return AutonomousVerdict.CRITICAL
        if bottlenecks:
            return AutonomousVerdict.WARNING
        return AutonomousVerdict.HEALTHY
