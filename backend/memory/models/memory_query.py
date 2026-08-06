"""MemoryQuery: a fully deterministic set of filters + ranking/limit knobs
for retrieving MemoryItems. No field here ever triggers an embedding
lookup or similarity search — every one is a plain, inspectable filter.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType


class MemoryQuery(BaseModel):
    """Deterministic retrieval filters: keyword/tag/type/scope/date/importance, plus top-k."""

    keyword: str | None = None
    tags: list[str] = Field(default_factory=list)
    memory_type: MemoryType | None = None
    scope: MemoryScope | None = None
    session_id: str | None = None
    user_id: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    min_importance: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, gt=0)
    recent_first: bool = True
