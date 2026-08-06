"""MemorySummarizer: deterministic, extractive summarization over a group of
MemoryItems — never an AI call.

Concatenates each item's own already-written ``title``/``summary``
(themselves written by whichever service created the memory — a
report's title, a plan's goal) into one combined block, oldest first,
truncated to a maximum length. Extractive, not abstractive: no new
sentence is ever generated, only existing text selected and joined.
"""

from backend.memory.models.memory_item import MemoryItem

DEFAULT_MAX_LENGTH = 800


class MemorySummarizer:
    """Deterministically combines several MemoryItems' own summaries into one block."""

    def summarize(self, items: list[MemoryItem], max_length: int = DEFAULT_MAX_LENGTH) -> str:
        """Join every item's ``title``/``summary`` (oldest first) into one truncated block."""
        if not items:
            return "No memories to summarize."
        ordered = sorted(items, key=lambda item: item.created_at)
        lines = [f"- {item.title}: {item.summary}" for item in ordered if item.summary]
        combined = "\n".join(lines)
        if len(combined) <= max_length:
            return combined
        return combined[: max_length - 1].rstrip() + "…"
