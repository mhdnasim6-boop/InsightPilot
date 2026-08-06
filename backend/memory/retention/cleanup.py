"""run_cleanup(): applies a RetentionPolicy against a MemoryStore, deleting
whatever RetentionEngine decides should be evicted.
"""

from backend.memory.models.retention_policy import RetentionPolicy
from backend.memory.retention.retention_engine import RetentionEngine
from backend.memory.store.memory_store import MemoryStore


def run_cleanup(store: MemoryStore, policy: RetentionPolicy, engine: RetentionEngine | None = None) -> list[str]:
    """Evict whatever ``policy`` says should go from ``store``. Returns the evicted memory_ids."""
    engine = engine or RetentionEngine()
    to_evict = engine.items_to_evict(store.list_all(), policy)
    for memory_id in to_evict:
        store.delete(memory_id)
    return to_evict
