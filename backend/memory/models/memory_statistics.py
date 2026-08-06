"""MemoryStatistics: derived, read-only aggregate counts over the memory store.

Mirrors ``ExecutionMetricsSummary``/``MemoryStatistics``-shaped models
elsewhere in this codebase (Observability & Tracing) — recomputed fresh
on every request, never stored or mutated itself.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class MemoryStatistics(BaseModel):
    """Aggregate counts and recency over every memory currently stored."""

    total_items: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_scope: dict[str, int] = Field(default_factory=dict)
    recent_activity_count: int = 0
    average_importance: float = 0.0
    oldest_item_at: datetime | None = None
    newest_item_at: datetime | None = None
