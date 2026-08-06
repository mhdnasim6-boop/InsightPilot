"""MemoryReference: a pointer from a MemoryItem to the real entity it's about.

Deliberately a plain (reference_type, reference_id) pair — never the
real domain object (``BusinessDataset``, ``ReportDocument``,
``ExecutionPlan``, ...) itself. That is what "Memory is Generic" means
structurally: the memory layer never imports, depends on, or even knows
the shape of any business model; it only remembers *which* dataset/
report/plan/execution/approval a memory concerns, by id, so a caller
that already holds the real object can look it up through its own
existing store (``BusinessDatasetStore``, ``ReportStore``, ...) —
the memory layer is never a second source of truth for it.
"""

from pydantic import BaseModel, ConfigDict


class MemoryReference(BaseModel):
    """A pointer to the real entity (by type and id) a MemoryItem is about."""

    model_config = ConfigDict(frozen=True)

    reference_type: str
    reference_id: str
