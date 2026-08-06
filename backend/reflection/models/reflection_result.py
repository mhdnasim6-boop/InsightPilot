"""ReflectionResult: what ReflectionService.generate() returns — identity/
provenance fields plus the analytical ExecutionReview itself.

``reflection_id`` *is* the ``MemoryItem.memory_id`` it gets stored under
(see ``ReflectionService`` — reflections have no store of their own,
``MemoryService`` is the only persistence layer). It is always empty at
construction time, inside ``ReflectionService.generate()``, since a
``MemoryItem``'s id is only known once ``MemoryService.remember()``
returns — the service patches it in via ``model_copy`` immediately after.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.reflection.models.execution_review import ExecutionReview


class ReflectionResult(BaseModel):
    """One complete reflection: identity/provenance plus its ExecutionReview."""

    model_config = ConfigDict(frozen=True)

    reflection_id: str
    plan_id: str
    session_id: str | None = None
    trace_id: str
    collaboration_id: str | None = None
    report_id: str | None = None
    review: ExecutionReview
    generated_at: datetime
