"""RetentionEngine: decides which MemoryItems a RetentionPolicy says should be
evicted — by age, then by capacity (overall and per-type), evicting the
least important/oldest items first. Deterministic; never calls AI.
"""

from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.retention_policy import RetentionPolicy
from backend.memory.retention.expiration import is_expired


class RetentionEngine:
    """Computes which memory_ids a RetentionPolicy says should be removed."""

    def items_to_evict(self, items: list[MemoryItem], policy: RetentionPolicy) -> list[str]:
        """Return the memory_ids ``policy`` says should be removed, given the full item list."""
        to_evict: set[str] = set()

        for item in items:
            if is_expired(item, policy.max_age_days):
                to_evict.add(item.memory_id)

        remaining = [item for item in items if item.memory_id not in to_evict]

        if policy.max_items_per_type is not None:
            by_type: dict[str, list[MemoryItem]] = {}
            for item in remaining:
                by_type.setdefault(item.memory_type.value, []).append(item)
            for grouped in by_type.values():
                to_evict.update(self._excess(grouped, policy.max_items_per_type))
            remaining = [item for item in remaining if item.memory_id not in to_evict]

        if policy.max_items is not None:
            to_evict.update(self._excess(remaining, policy.max_items))

        return sorted(to_evict)

    def _excess(self, items: list[MemoryItem], limit: int) -> list[str]:
        if len(items) <= limit:
            return []
        # Keep the most important, most recent items; evict the rest.
        ranked = sorted(items, key=lambda item: (item.importance, item.created_at), reverse=True)
        return [item.memory_id for item in ranked[limit:]]
