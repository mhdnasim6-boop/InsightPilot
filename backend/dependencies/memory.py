"""Memory layer providers: store and the top-level MemoryService.

Mirrors the rest of this package's caching convention: ``MemoryStore``
is a process-wide singleton (like ``TraceStore``/``ApprovalStore``/
``ExecutionCheckpointStore``) since a memory written in one request must
be recallable in a later one. ``MemoryService`` is cached too — unlike
``ExecutionService`` (deliberately left uncached; see
``backend.dependencies.execution``'s own docstring for why), every one
of ``MemoryService``'s constructor dependencies here is itself either an
already-cached singleton (``MemoryStore``, ``ObservabilityService``) or
a stateless, cheap-to-construct helper (``RetrievalEngine``,
``MemorySummarizer``, the exporters) — nothing varies in identity
between requests, so ``@lru_cache`` genuinely hits its cache.
"""

from functools import lru_cache
from typing import Any

from fastapi import Depends

from backend.dependencies.observability import get_observability_service
from backend.dependencies.realtime import get_realtime_service
from backend.memory.exporters.json_exporter import JSONMemoryExporter
from backend.memory.exporters.markdown_exporter import MarkdownMemoryExporter
from backend.memory.retrieval.retrieval_engine import RetrievalEngine
from backend.memory.services.memory_service import MemoryService
from backend.memory.store.memory_store import MemoryStore
from backend.memory.summarization.memory_summarizer import MemorySummarizer
from backend.observability.services.observability_service import ObservabilityService
from backend.realtime.publishers.memory_publisher import RealtimePublishingMemoryService
from backend.realtime.services.realtime_service import RealtimeService


@lru_cache
def get_memory_store() -> MemoryStore:
    """Return the process-wide MemoryStore singleton."""
    return MemoryStore()


@lru_cache
def get_memory_service(
    store: MemoryStore = Depends(get_memory_store),
    observability_service: ObservabilityService = Depends(get_observability_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> MemoryService:
    """Return the process-wide MemoryService singleton — the only object anything should use for memory.

    Wrapped in ``RealtimePublishingMemoryService`` (Phase 37) before being
    returned — publishes MemoryStored after every ``remember()`` with no
    change to ``MemoryService`` itself. Wrapping at this single cached
    source covers every consumer in the app (agents, ``ApprovalService``,
    ``ReflectionService``, ``WorkflowService``) transparently.
    """
    service: Any = RealtimePublishingMemoryService(
        MemoryService(
            store=store,
            retrieval_engine=RetrievalEngine(),
            summarizer=MemorySummarizer(),
            json_exporter=JSONMemoryExporter(),
            markdown_exporter=MarkdownMemoryExporter(),
            observability_service=observability_service,
        ),
        realtime_service,
    )
    return service
