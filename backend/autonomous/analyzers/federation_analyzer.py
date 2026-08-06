"""FederationAnalyzer: Cluster utilization.

Reuses ``FederationService.federation_statistics()`` (Phase 39) and
``FederationService.list_routing_decisions()`` outright — never a raw
recomputation. Reroute activity (``RoutingDecision.reroute_count > 0``)
is a direct, honest signal of cluster instability: it only ever happens
when ``FailoverManager`` had to move a still-PENDING decision off a
cluster that had gone unavailable.
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
from backend.federation.models.federation_statistics import FederationStatistics
from backend.federation.models.routing_decision import RoutingDecision
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

UNAVAILABLE_CLUSTER_RATIO_WARNING = 0.25
UNAVAILABLE_CLUSTER_RATIO_CRITICAL = 0.5
CAPACITY_UTILIZATION_WARNING = 0.8


class FederationAnalyzer:
    """Detects cluster-availability and cluster-capacity bottlenecks."""

    def analyze(
        self, federation_statistics: FederationStatistics, routing_decisions: list[RoutingDecision],
    ) -> tuple[list[Bottleneck], AutonomousDecision]:
        bottlenecks: list[Bottleneck] = []
        now = utc_now()

        if federation_statistics.total_clusters > 0:
            unavailable = federation_statistics.offline_clusters + federation_statistics.failed_clusters
            ratio = unavailable / federation_statistics.total_clusters
            if ratio >= UNAVAILABLE_CLUSTER_RATIO_CRITICAL:
                bottlenecks.append(self._bottleneck(
                    BottleneckSeverity.CRITICAL, "Most clusters are unavailable",
                    f"{unavailable}/{federation_statistics.total_clusters} cluster(s) ({ratio:.0%}) are OFFLINE/FAILED.",
                    "unavailable_cluster_ratio", ratio, UNAVAILABLE_CLUSTER_RATIO_CRITICAL, now,
                ))
            elif ratio >= UNAVAILABLE_CLUSTER_RATIO_WARNING:
                bottlenecks.append(self._bottleneck(
                    BottleneckSeverity.MEDIUM, "A significant share of clusters are unavailable",
                    f"{unavailable}/{federation_statistics.total_clusters} cluster(s) ({ratio:.0%}) are OFFLINE/FAILED.",
                    "unavailable_cluster_ratio", ratio, UNAVAILABLE_CLUSTER_RATIO_WARNING, now,
                ))

        if federation_statistics.total_capacity > 0:
            utilization = federation_statistics.active_remote_executions / federation_statistics.total_capacity
            if utilization >= CAPACITY_UTILIZATION_WARNING:
                bottlenecks.append(self._bottleneck(
                    BottleneckSeverity.MEDIUM, "Federation-wide capacity is nearly exhausted",
                    f"{federation_statistics.active_remote_executions}/{federation_statistics.total_capacity} "
                    f"({utilization:.0%}) of federation-wide concurrent-execution capacity is in use.",
                    "capacity_utilization", utilization, CAPACITY_UTILIZATION_WARNING, now,
                ))

        rerouted = [d for d in routing_decisions if d.reroute_count > 0]
        if rerouted:
            bottlenecks.append(self._bottleneck(
                BottleneckSeverity.LOW, "Routing decisions have been rerouted due to cluster unavailability",
                f"{len(rerouted)}/{len(routing_decisions)} routing decision(s) required at least one reroute.",
                "rerouted_decision_count", float(len(rerouted)), 0.0, now,
            ))

        verdict = self._verdict(bottlenecks)
        decision = AutonomousDecision(
            decision_id=generate_id(), analyzer_name="FederationAnalyzer", verdict=verdict,
            bottleneck_ids=[b.bottleneck_id for b in bottlenecks],
            notes=f"{len(bottlenecks)} bottleneck(s) detected across cluster availability/capacity signals.",
            decided_at=now,
        )
        return bottlenecks, decision

    def _bottleneck(
        self, severity: BottleneckSeverity, title: str, description: str,
        metric_name: str, metric_value: float, threshold: float, now: datetime,
    ) -> Bottleneck:
        return Bottleneck(
            bottleneck_id=generate_id(), category=BottleneckCategory.CLUSTER_UTILIZATION, severity=severity,
            title=title, description=description, metric_name=metric_name, metric_value=metric_value,
            threshold=threshold, source="FederationAnalyzer", detected_at=now,
        )

    def _verdict(self, bottlenecks: list[Bottleneck]) -> AutonomousVerdict:
        if any(b.severity in {BottleneckSeverity.HIGH, BottleneckSeverity.CRITICAL} for b in bottlenecks):
            return AutonomousVerdict.CRITICAL
        if bottlenecks:
            return AutonomousVerdict.WARNING
        return AutonomousVerdict.HEALTHY
