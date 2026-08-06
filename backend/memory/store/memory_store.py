"""MemoryStore: in-memory memory_id -> MemoryItem storage, with secondary
indexes for fast type/scope/tag filtering.

Mirrors every other ``*Store`` in this codebase (``TraceStore``,
``ApprovalStore``, ``ExecutionCheckpointStore``) — a plain dict,
process-wide singleton via DI, no persistence backend yet, pure CRUD
only. Search/statistics/export are deliberately *not* methods here: they
are cross-cutting reads over whatever this store holds, computed by
dedicated collaborators (``RetrievalEngine``, ``StatisticsService``,
the exporters) that ``MemoryService`` composes — exactly how
``TraceStore`` stays pure storage while ``MetricsService``/
``TraceExporter`` do the richer reads elsewhere. Nothing outside
``backend/memory/`` should import this class directly; every external
caller goes through ``MemoryService``.
"""

from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.store.indexes import MemoryIndexes


class MemoryStore:
    """Process-wide store of MemoryItems, keyed by memory_id."""

    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}
        self._indexes = MemoryIndexes()

    def add(self, item: MemoryItem) -> MemoryItem:
        """Store a new memory, keyed by its own ``memory_id``."""
        self._items[item.memory_id] = item
        self._indexes.add(item)
        return item

    def update(self, item: MemoryItem) -> MemoryItem:
        """Replace an existing memory (by ``memory_id``), keeping indexes in sync."""
        existing = self._items.get(item.memory_id)
        if existing is not None:
            self._indexes.remove(existing)
        self._items[item.memory_id] = item
        self._indexes.add(item)
        return item

    def delete(self, memory_id: str) -> bool:
        """Remove a memory. Returns whether one was actually removed."""
        existing = self._items.pop(memory_id, None)
        if existing is None:
            return False
        self._indexes.remove(existing)
        return True

    def get(self, memory_id: str) -> MemoryItem | None:
        """Return the memory for a memory_id, or None if not present."""
        return self._items.get(memory_id)

    def list_all(self) -> list[MemoryItem]:
        """Return every stored memory, most recently added first."""
        return list(reversed(self._items.values()))

    def list_by_type(self, memory_type: MemoryType) -> list[MemoryItem]:
        """Return every memory of ``memory_type``, most recently added first."""
        ids = self._indexes.by_type(memory_type)
        return [item for item in self.list_all() if item.memory_id in ids]

    def list_by_scope(self, scope: MemoryScope) -> list[MemoryItem]:
        """Return every memory in ``scope``, most recently added first."""
        ids = self._indexes.by_scope(scope)
        return [item for item in self.list_all() if item.memory_id in ids]

    def list_by_tag(self, tag: str) -> list[MemoryItem]:
        """Return every memory tagged with ``tag``, most recently added first."""
        ids = self._indexes.by_tag(tag)
        return [item for item in self.list_all() if item.memory_id in ids]

    def clear(self) -> None:
        """Remove every stored memory."""
        self._items.clear()
        self._indexes.clear()

    def count(self) -> int:
        """Total number of memories currently stored."""
        return len(self._items)
