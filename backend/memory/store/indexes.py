"""MemoryIndexes: secondary, in-memory indexes over MemoryItems for fast filtering.

Plain ``dict[key, set[memory_id]]`` indexes, kept in sync on every
add/remove — the same role a database's secondary index plays, scaled
down to this store's in-memory scope. ``MemoryStore`` is the only
caller; nothing else should touch this class.
"""

from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType


class MemoryIndexes:
    """Type/scope/tag -> set[memory_id] indexes, maintained incrementally."""

    def __init__(self) -> None:
        self._by_type: dict[MemoryType, set[str]] = {}
        self._by_scope: dict[MemoryScope, set[str]] = {}
        self._by_tag: dict[str, set[str]] = {}

    def add(self, item: MemoryItem) -> None:
        """Index ``item`` under its type, scope, and every tag."""
        self._by_type.setdefault(item.memory_type, set()).add(item.memory_id)
        self._by_scope.setdefault(item.scope, set()).add(item.memory_id)
        for tag in item.tags:
            self._by_tag.setdefault(tag, set()).add(item.memory_id)

    def remove(self, item: MemoryItem) -> None:
        """Un-index ``item`` from its type, scope, and every tag."""
        self._by_type.get(item.memory_type, set()).discard(item.memory_id)
        self._by_scope.get(item.scope, set()).discard(item.memory_id)
        for tag in item.tags:
            self._by_tag.get(tag, set()).discard(item.memory_id)

    def by_type(self, memory_type: MemoryType) -> set[str]:
        """memory_ids currently indexed under ``memory_type``."""
        return set(self._by_type.get(memory_type, set()))

    def by_scope(self, scope: MemoryScope) -> set[str]:
        """memory_ids currently indexed under ``scope``."""
        return set(self._by_scope.get(scope, set()))

    def by_tag(self, tag: str) -> set[str]:
        """memory_ids currently indexed under ``tag``."""
        return set(self._by_tag.get(tag, set()))

    def clear(self) -> None:
        """Drop every index entry."""
        self._by_type.clear()
        self._by_scope.clear()
        self._by_tag.clear()
