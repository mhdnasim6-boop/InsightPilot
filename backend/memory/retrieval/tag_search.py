"""Deterministic tag search over MemoryItems — exact (case-insensitive) tag
membership only. Never a fuzzy or semantic tag comparison.
"""

from backend.memory.models.memory_item import MemoryItem


def matches_any_tag(item: MemoryItem, tags: list[str]) -> bool:
    """Whether ``item`` carries at least one of ``tags`` (case-insensitive)."""
    if not tags:
        return True
    item_tags = {tag.lower() for tag in item.tags}
    return any(tag.lower() in item_tags for tag in tags)


def tag_match_count(item: MemoryItem, tags: list[str]) -> int:
    """How many of ``tags`` ``item`` carries — used for ranking."""
    if not tags:
        return 0
    item_tags = {tag.lower() for tag in item.tags}
    return sum(1 for tag in tags if tag.lower() in item_tags)
