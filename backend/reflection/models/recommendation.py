"""Recommendation: one deterministic, actionable suggestion for next time.

Never AI-generated — every recommendation is produced by a plain rule in
``backend.reflection.analyzers.recommendation_engine`` reacting to a
specific, inspectable fact in the analyzed data (a failed tool, an
approval delay, a memory hit/miss, ...). ``reason`` always names that
fact, so a recommendation is never a black box.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict


class RecommendationCategory(str, Enum):
    """What kind of change a Recommendation suggests."""

    TOOL_CHOICE = "tool_choice"
    PARALLELIZATION = "parallelization"
    CACHING = "caching"
    MEMORY_REUSE = "memory_reuse"
    APPROVAL_POLICY = "approval_policy"
    RETRY = "retry"
    OTHER = "other"


class RecommendationPriority(str, Enum):
    """How strongly a Recommendation should be acted on."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Recommendation(BaseModel):
    """One actionable, deterministic suggestion for a future, similar execution."""

    model_config = ConfigDict(frozen=True)

    recommendation_id: str
    category: RecommendationCategory
    message: str
    priority: RecommendationPriority
    reason: str
