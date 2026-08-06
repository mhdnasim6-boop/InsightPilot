"""Deterministic keyword search over MemoryItems — case-insensitive substring
matching against title/summary/tags. Never an embedding or semantic comparison.
"""

from backend.memory.models.memory_item import MemoryItem


def _haystack(item: MemoryItem) -> str:
    return " ".join([item.title, item.summary, *item.tags]).lower()


def keyword_matches(item: MemoryItem, keyword: str) -> bool:
    """Whether ``keyword`` appears (case-insensitively) in ``item``'s title, summary, or tags."""
    needle = keyword.strip().lower()
    if not needle:
        return True
    return needle in _haystack(item)


def keyword_match_count(item: MemoryItem, keyword: str) -> int:
    """How many times ``keyword`` appears in title+summary+tags — used for ranking."""
    needle = keyword.strip().lower()
    if not needle:
        return 0
    return _haystack(item).count(needle)
