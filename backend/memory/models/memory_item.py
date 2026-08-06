"""MemoryItem: one piece of structured, generic knowledge stored in the memory layer.

``content`` is a plain ``dict``, never a domain model
(``BusinessDataset``, ``ReportDocument``, ``AnalysisResult``, ...) —
that is what makes memory generic: it never depends on, or even
imports, any business model. A caller that wants the real object back
uses ``references`` (by type + id) to look it up through its own
already-existing store. ``session_id``/``user_id`` — needed to filter
SESSION/USER-scoped memories — live in ``metadata`` rather than as
dedicated fields, the same reasoning ``ExecutionApproval`` already
established for ``node_name``/``execution_id``: they are retrieval
plumbing a caller reads (``metadata["session_id"]``), never something
this model needs to validate or reason about itself.

Frozen, like every other historical-record model in this codebase
(``ExecutionTrace``, ``ExecutionApproval``, ``ExecutionPlan``) —
``update()`` on ``MemoryStore`` produces a new instance via
``model_copy``, never in-place mutation.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.memory.models.memory_reference import MemoryReference
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType


class MemoryItem(BaseModel):
    """One immutable, generic piece of knowledge the memory layer stores."""

    model_config = ConfigDict(frozen=True)

    memory_id: str
    title: str
    summary: str
    content: dict[str, Any] = Field(default_factory=dict)
    memory_type: MemoryType
    scope: MemoryScope
    created_at: datetime
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    references: list[MemoryReference] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
