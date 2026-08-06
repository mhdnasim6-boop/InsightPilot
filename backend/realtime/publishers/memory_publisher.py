"""MemoryPublisher: MemoryStored.

Wraps ``MemoryService`` — every other method (``recall``, ``search``,
``summarize``, the exporters, ...) is forwarded unchanged via
``__getattr__``. Wired into ``get_memory_service()``
(``backend.dependencies.memory``), the single cached singleton every
consumer in the app (agents, ``ApprovalService``, ``ReflectionService``,
``WorkflowService``) already shares, so wrapping there covers every
memory write in the system, whatever triggered it.
"""

from typing import Any

from backend.memory.models.memory_item import MemoryItem
from backend.memory.models.memory_reference import MemoryReference
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.realtime.events.event import Event
from backend.realtime.events.event_type import EventType
from backend.realtime.services.realtime_service import RealtimeService


class RealtimePublishingMemoryService:
    """Wraps a real MemoryService, publishing MemoryStored after every ``remember()``."""

    def __init__(self, inner: MemoryService, realtime_service: RealtimeService) -> None:
        self._inner = inner
        self._realtime_service = realtime_service

    def remember(
        self,
        title: str,
        summary: str,
        memory_type: MemoryType,
        scope: MemoryScope = MemoryScope.SESSION,
        content: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        importance: float = 0.5,
        references: list[MemoryReference] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        item = self._inner.remember(
            title, summary, memory_type, scope, content, tags, importance, references, metadata
        )
        self._publish(item)
        return item

    def _publish(self, item: MemoryItem) -> None:
        plan_id = next((ref.reference_id for ref in item.references if ref.reference_type == "plan"), None)
        self._realtime_service.publish(
            Event(
                event_type=EventType.MEMORY_STORED,
                plan_id=plan_id,
                data={
                    "memory_id": item.memory_id,
                    "title": item.title,
                    "memory_type": item.memory_type.value,
                    "scope": item.scope.value,
                },
            )
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
