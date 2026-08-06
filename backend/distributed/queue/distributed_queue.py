"""DistributedQueue: a generic, ordered, key-addressable in-memory store.

Not a strict FIFO pop-only queue — ``TaskQueue``/``RetryQueue`` both need
constant-time lookup by ``assignment_id`` (``complete()``/``fail()``
resolve one specific assignment, not just "the next one"), so this is an
insertion-ordered ``dict`` wrapper, mirroring every other in-memory
``*Store`` in this codebase (``ApprovalStore``, ``MemoryStore``) rather
than a literal ``collections.deque``.
"""

from typing import Generic, TypeVar

ItemT = TypeVar("ItemT")


class DistributedQueue(Generic[ItemT]):
    """Insertion-ordered, key-addressable in-memory queue."""

    def __init__(self) -> None:
        self._items: dict[str, ItemT] = {}

    def enqueue(self, key: str, item: ItemT) -> ItemT:
        """Add (or replace) one item, keyed by ``key``."""
        self._items[key] = item
        return item

    def get(self, key: str) -> ItemT | None:
        """Return the item for ``key``, or None if not queued."""
        return self._items.get(key)

    def remove(self, key: str) -> ItemT | None:
        """Remove and return the item for ``key``. None if it wasn't queued."""
        return self._items.pop(key, None)

    def list_all(self) -> list[ItemT]:
        """Every currently queued item, oldest first."""
        return list(self._items.values())

    def __len__(self) -> int:
        return len(self._items)
