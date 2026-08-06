"""ObservabilityAnalyzer: AI usage and Tool usage (which implicitly covers Plugin usage).

Reuses ``MetricsService.tool_metrics()``/``.ai_metrics()`` (Phase 24)
outright. A plugin-contributed tool (Phase 33) registers into the exact
same ``ToolRegistry`` and is traced through the exact same ``TracingTool``
path as every first-party tool, so it already appears in
``tool_metrics()`` indistinguishably — this analyzer does not need
``PluginRegistry`` at all to give Plugin usage genuine coverage; findings
about any tool with an unrecognized/plugin-style name still surface here
as ordinary tool-usage bottlenecks.
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
from backend.observability.metrics.models import AIMetrics, ToolMetrics
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

TOOL_FAILURE_RATE_WARNING = 0.2
TOOL_FAILURE_RATE_CRITICAL = 0.5
TOOL_LATENCY_WARNING_MS = 10_000.0
AI_LATENCY_WARNING_MS = 15_000.0


class ObservabilityAnalyzer:
    """Detects tool-failure-rate, tool-latency, and AI-latency bottlenecks."""

    def analyze(self, tool_metrics: list[ToolMetrics], ai_metrics: AIMetrics) -> tuple[list[Bottleneck], AutonomousDecision]:
        bottlenecks: list[Bottleneck] = []
        now = utc_now()

        for metrics in tool_metrics:
            if metrics.call_count == 0:
                continue
            failure_rate = metrics.failed_count / metrics.call_count
            if failure_rate >= TOOL_FAILURE_RATE_CRITICAL:
                bottlenecks.append(self._bottleneck(
                    BottleneckCategory.TOOL_USAGE, BottleneckSeverity.HIGH,
                    f"Tool '{metrics.tool_name}' is failing most of the time",
                    f"{metrics.failed_count}/{metrics.call_count} call(s) ({failure_rate:.0%}) failed.",
                    "failure_rate", failure_rate, TOOL_FAILURE_RATE_CRITICAL, now,
                    {"tool_name": metrics.tool_name},
                ))
            elif failure_rate >= TOOL_FAILURE_RATE_WARNING:
                bottlenecks.append(self._bottleneck(
                    BottleneckCategory.TOOL_USAGE, BottleneckSeverity.MEDIUM,
                    f"Tool '{metrics.tool_name}' has an elevated failure rate",
                    f"{metrics.failed_count}/{metrics.call_count} call(s) ({failure_rate:.0%}) failed.",
                    "failure_rate", failure_rate, TOOL_FAILURE_RATE_WARNING, now,
                    {"tool_name": metrics.tool_name},
                ))
            if metrics.average_duration_ms >= TOOL_LATENCY_WARNING_MS:
                bottlenecks.append(self._bottleneck(
                    BottleneckCategory.TOOL_USAGE, BottleneckSeverity.LOW,
                    f"Tool '{metrics.tool_name}' has elevated latency",
                    f"Average call duration is {metrics.average_duration_ms:.0f}ms across {metrics.call_count} call(s).",
                    "average_duration_ms", metrics.average_duration_ms, TOOL_LATENCY_WARNING_MS, now,
                    {"tool_name": metrics.tool_name},
                ))

        if ai_metrics.call_count > 0 and ai_metrics.average_latency_ms >= AI_LATENCY_WARNING_MS:
            bottlenecks.append(self._bottleneck(
                BottleneckCategory.AI_USAGE, BottleneckSeverity.MEDIUM,
                "AI provider calls have elevated latency",
                f"Average AI call latency is {ai_metrics.average_latency_ms:.0f}ms across {ai_metrics.call_count} call(s).",
                "average_latency_ms", ai_metrics.average_latency_ms, AI_LATENCY_WARNING_MS, now,
            ))

        verdict = self._verdict(bottlenecks)
        decision = AutonomousDecision(
            decision_id=generate_id(), analyzer_name="ObservabilityAnalyzer", verdict=verdict,
            bottleneck_ids=[b.bottleneck_id for b in bottlenecks],
            notes=f"{len(bottlenecks)} bottleneck(s) detected across tool/AI usage signals.",
            decided_at=now,
        )
        return bottlenecks, decision

    def _bottleneck(
        self, category: BottleneckCategory, severity: BottleneckSeverity, title: str, description: str,
        metric_name: str, metric_value: float, threshold: float, now: datetime, metadata: dict | None = None,
    ) -> Bottleneck:
        return Bottleneck(
            bottleneck_id=generate_id(), category=category, severity=severity, title=title, description=description,
            metric_name=metric_name, metric_value=metric_value, threshold=threshold, source="ObservabilityAnalyzer",
            detected_at=now, metadata=metadata or {},
        )

    def _verdict(self, bottlenecks: list[Bottleneck]) -> AutonomousVerdict:
        if any(b.severity in {BottleneckSeverity.HIGH, BottleneckSeverity.CRITICAL} for b in bottlenecks):
            return AutonomousVerdict.CRITICAL
        if bottlenecks:
            return AutonomousVerdict.WARNING
        return AutonomousVerdict.HEALTHY
