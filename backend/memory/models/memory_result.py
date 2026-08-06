"""MemoryResult: the outcome of one retrieval — the matched items, how many
matched before top-k truncation, and the query that produced them (for
traceability/debugging, not re-execution).
"""

from pydantic import BaseModel, Field

from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.memory_query import MemoryQuery


class MemoryResult(BaseModel):
    """One retrieval's matched items, plus how many matched in total."""

    items: list[MemoryItem] = Field(default_factory=list)
    total_matched: int = 0
    query: MemoryQuery | None = None
