"""Request bodies for the Memory REST endpoints."""

from typing import Any

from pydantic import BaseModel, Field

from backend.memory.models.memory_query import MemoryQuery
from backend.memory.models.memory_reference import MemoryReference
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.summarization.memory_summarizer import DEFAULT_MAX_LENGTH


class MemoryCreateRequest(BaseModel):
    """Everything ``MemoryService.remember()`` needs to create one MemoryItem."""

    title: str
    summary: str
    memory_type: MemoryType
    scope: MemoryScope = MemoryScope.SESSION
    content: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    references: list[MemoryReference] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemorySummarizeRequest(BaseModel):
    """Which memories to summarize (or all, if ``query`` is omitted), and how long."""

    query: MemoryQuery | None = None
    max_length: int = Field(default=DEFAULT_MAX_LENGTH, gt=0)
