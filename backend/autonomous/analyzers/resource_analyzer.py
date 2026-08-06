"""ResourceAnalyzer: Memory utilization and Security overhead.

Reuses ``MemoryService.statistics()`` (Phase 29) outright. Security
overhead reuses ``AuditService.total_events()`` (Phase 35) — a light,
read-only touch: this phase's own "Reuse" list doesn't name
``AuditService`` explicitly, but reading (never modifying) its own
already-computed event count is the same "don't duplicate, don't
recompute" discipline applied to one more existing read-only surface,
not a new security-layer dependency of any weight.
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
from backend.memory.models.memory_statistics import MemoryStatistics
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

MEMORY_ITEM_COUNT_WARNING = 5_000
MEMORY_ITEM_COUNT_CRITICAL = 20_000
LOW_IMPORTANCE_WARNING = 0.3
AUDIT_EVENT_VOLUME_WARNING = 500


class ResourceAnalyzer:
    """Detects memory-growth, low-value-memory, and audit-volume bottlenecks."""

    def analyze(
        self, memory_statistics: MemoryStatistics, audit_event_count: int,
    ) -> tuple[list[Bottleneck], AutonomousDecision]:
        bottlenecks: list[Bottleneck] = []
        now = utc_now()

        if memory_statistics.total_items >= MEMORY_ITEM_COUNT_CRITICAL:
            bottlenecks.append(self._bottleneck(
                BottleneckCategory.MEMORY_UTILIZATION, BottleneckSeverity.HIGH,
                "Stored memory volume is very high",
                f"{memory_statistics.total_items} memory item(s) are currently stored — consider a retention review.",
                "total_items", float(memory_statistics.total_items), float(MEMORY_ITEM_COUNT_CRITICAL), now,
            ))
        elif memory_statistics.total_items >= MEMORY_ITEM_COUNT_WARNING:
            bottlenecks.append(self._bottleneck(
                BottleneckCategory.MEMORY_UTILIZATION, BottleneckSeverity.MEDIUM,
                "Stored memory volume is growing",
                f"{memory_statistics.total_items} memory item(s) are currently stored.",
                "total_items", float(memory_statistics.total_items), float(MEMORY_ITEM_COUNT_WARNING), now,
            ))

        if memory_statistics.total_items > 0 and memory_statistics.average_importance <= LOW_IMPORTANCE_WARNING:
            bottlenecks.append(self._bottleneck(
                BottleneckCategory.MEMORY_UTILIZATION, BottleneckSeverity.LOW,
                "Stored memories skew toward low importance",
                f"Average importance is {memory_statistics.average_importance:.2f} across "
                f"{memory_statistics.total_items} item(s).",
                "average_importance", memory_statistics.average_importance, LOW_IMPORTANCE_WARNING, now,
            ))

        if audit_event_count >= AUDIT_EVENT_VOLUME_WARNING:
            bottlenecks.append(self._bottleneck(
                BottleneckCategory.SECURITY_OVERHEAD, BottleneckSeverity.LOW,
                "Audit event volume is high",
                f"{audit_event_count} audit event(s) are currently recorded — mostly informational, "
                "worth a periodic review.",
                "audit_event_count", float(audit_event_count), float(AUDIT_EVENT_VOLUME_WARNING), now,
            ))

        verdict = self._verdict(bottlenecks)
        decision = AutonomousDecision(
            decision_id=generate_id(), analyzer_name="ResourceAnalyzer", verdict=verdict,
            bottleneck_ids=[b.bottleneck_id for b in bottlenecks],
            notes=f"{len(bottlenecks)} bottleneck(s) detected across memory/audit signals.",
            decided_at=now,
        )
        return bottlenecks, decision

    def _bottleneck(
        self, category: BottleneckCategory, severity: BottleneckSeverity, title: str, description: str,
        metric_name: str, metric_value: float, threshold: float, now: datetime,
    ) -> Bottleneck:
        return Bottleneck(
            bottleneck_id=generate_id(), category=category, severity=severity, title=title, description=description,
            metric_name=metric_name, metric_value=metric_value, threshold=threshold, source="ResourceAnalyzer",
            detected_at=now,
        )

    def _verdict(self, bottlenecks: list[Bottleneck]) -> AutonomousVerdict:
        if any(b.severity in {BottleneckSeverity.HIGH, BottleneckSeverity.CRITICAL} for b in bottlenecks):
            return AutonomousVerdict.CRITICAL
        if bottlenecks:
            return AutonomousVerdict.WARNING
        return AutonomousVerdict.HEALTHY
