"""HealingRecommendation: one self-healing suggestion, always advisory.

``requires_human_approval`` is fixed ``True`` (not a default) — the same
structural-not-conventional enforcement ``OptimizationAction.safe_to_automate``
uses. ``HealingValidator`` (``backend/autonomous/healing/healing_validator.py``)
re-checks this invariant explicitly before a recommendation is ever
allowed into a report, so the guarantee holds even if a future strategy
implementation tried to construct one incorrectly.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.autonomous.models.bottleneck import BottleneckCategory


class HealingRecommendation(BaseModel):
    """One human-reviewed, advisory-only healing suggestion for a detected Bottleneck."""

    model_config = ConfigDict(frozen=True)

    recommendation_id: str
    bottleneck_id: str
    action_id: str | None = None
    category: BottleneckCategory
    strategy_name: str
    title: str
    description: str
    rationale: str
    risk_level: Literal["low", "medium", "high"]
    requires_human_approval: Literal[True] = True
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
