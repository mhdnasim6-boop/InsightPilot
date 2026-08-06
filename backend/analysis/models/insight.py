"""Deterministic, rule-based business insights. No AI, no LLM calls — every
insight here is reproducible from ``InsightEngine``'s fixed rules and the
already-computed analysis sections.
"""

from typing import Any

from pydantic import BaseModel, Field


class Insight(BaseModel):
    """One rule-generated, human-readable fact about the dataset."""

    category: str
    message: str
    metric: str | None = None
    value: float | None = None
    supporting_data: dict[str, Any] = Field(default_factory=dict)
