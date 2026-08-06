"""is_expired(): deterministic age-based expiration check for one MemoryItem."""

from datetime import timedelta

from backend.memory.models.memory_item import MemoryItem
from backend.utils.time import utc_now


def is_expired(item: MemoryItem, max_age_days: float | None) -> bool:
    """Whether ``item`` is older than ``max_age_days``. ``None`` means it never expires."""
    if max_age_days is None:
        return False
    return utc_now() - item.created_at > timedelta(days=max_age_days)
