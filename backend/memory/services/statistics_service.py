"""StatisticsService: derived, read-only aggregate statistics over a MemoryStore.

Mirrors ``MetricsService``'s own "pure, stateless, recomputed on every
call" design (Observability & Tracing Architecture) — nothing here is
stored; every field is computed fresh from whatever the store currently
holds.
"""

from datetime import timedelta

from backend.memory.models.memory_statistics import MemoryStatistics
from backend.memory.store.memory_store import MemoryStore
from backend.utils.time import utc_now


class StatisticsService:
    """Computes a MemoryStatistics snapshot from a MemoryStore."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def compute(self) -> MemoryStatistics:
        """Return current aggregate counts, recency, and average importance."""
        items = self._store.list_all()
        if not items:
            return MemoryStatistics()

        by_type: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        for item in items:
            by_type[item.memory_type.value] = by_type.get(item.memory_type.value, 0) + 1
            by_scope[item.scope.value] = by_scope.get(item.scope.value, 0) + 1

        recent_cutoff = utc_now() - timedelta(hours=24)
        recent_activity_count = sum(1 for item in items if item.created_at >= recent_cutoff)
        created_ats = [item.created_at for item in items]

        return MemoryStatistics(
            total_items=len(items),
            by_type=by_type,
            by_scope=by_scope,
            recent_activity_count=recent_activity_count,
            average_importance=sum(item.importance for item in items) / len(items),
            oldest_item_at=min(created_ats),
            newest_item_at=max(created_ats),
        )
