"""Bottleneck: one detected inefficiency, derived from an already-reused
service's own statistics — never a raw recomputation.

``BottleneckCategory`` names all twelve optimization categories this
phase specifies; several are produced by the same analyzer where the
underlying data naturally comes from one reused service's own
``.statistics()`` call (see each ``analyzers/*.py`` module's own
docstring for exactly which categories it covers and why).
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BottleneckCategory(str, Enum):
    """Every optimization category this phase's analyzers can detect."""

    EXECUTION_EFFICIENCY = "execution_efficiency"
    WORKFLOW_EFFICIENCY = "workflow_efficiency"
    PARALLELISM = "parallelism"
    WORKER_UTILIZATION = "worker_utilization"
    CLUSTER_UTILIZATION = "cluster_utilization"
    APPROVAL_BOTTLENECK = "approval_bottleneck"
    REFLECTION_TRENDS = "reflection_trends"
    MEMORY_UTILIZATION = "memory_utilization"
    AI_USAGE = "ai_usage"
    TOOL_USAGE = "tool_usage"
    PLUGIN_USAGE = "plugin_usage"
    SECURITY_OVERHEAD = "security_overhead"


class BottleneckSeverity(str, Enum):
    """How urgently a detected bottleneck deserves attention."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Bottleneck(BaseModel):
    """One detected inefficiency: what metric, from which reused service, crossed what threshold."""

    model_config = ConfigDict(frozen=True)

    bottleneck_id: str
    category: BottleneckCategory
    severity: BottleneckSeverity
    title: str
    description: str
    metric_name: str
    metric_value: float
    threshold: float
    source: str
    detected_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
