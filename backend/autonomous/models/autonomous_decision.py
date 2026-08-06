"""AutonomousDecision: one analyzer's own top-level verdict for a single analysis pass.

Not an *action* the platform takes — the name mirrors "the analyzer's
decision about what it found," e.g. "ExecutionAnalyzer decided: 2
bottlenecks, HEALTHY overall" — purely a triage summary, one per
analyzer per report, letting a reader skim a report's health without
reading every individual ``Bottleneck``.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AutonomousVerdict(str, Enum):
    """One analyzer's own coarse health verdict for a single analysis pass."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class AutonomousDecision(BaseModel):
    """One analyzer's own top-level verdict, produced once per analysis pass."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    analyzer_name: str
    verdict: AutonomousVerdict
    bottleneck_ids: list[str] = Field(default_factory=list)
    notes: str = ""
    decided_at: datetime
