"""Reflection layer providers: the top-level ReflectionService.

Cached (unlike ``ExecutionService``/``CollaborationService``): every one
of ``ReflectionService``'s own dependencies here is itself an
already-cached singleton (``MemoryService``, ``ObservabilityService``) —
nothing varies in identity between requests, so ``@lru_cache`` genuinely
hits its cache, the same reasoning ``backend.dependencies.memory``'s own
docstring gives for ``MemoryService`` itself. ``ReflectionService`` holds
no store of its own (see its own docstring — Memory is the only
persistence layer), so there is no per-instance state to worry about
losing across requests either way.
"""

from functools import lru_cache
from typing import Any

from fastapi import Depends

from backend.dependencies.memory import get_memory_service
from backend.dependencies.observability import get_observability_service
from backend.dependencies.realtime import get_realtime_service
from backend.memory.services.memory_service import MemoryService
from backend.observability.services.observability_service import ObservabilityService
from backend.realtime.publishers.workflow_publisher import (
    RealtimePublishingReflectionService,
)
from backend.realtime.services.realtime_service import RealtimeService
from backend.reflection.services.reflection_service import ReflectionService


@lru_cache
def get_reflection_service(
    memory_service: MemoryService = Depends(get_memory_service),
    observability_service: ObservabilityService = Depends(get_observability_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> ReflectionService:
    """Provide the ReflectionService — the only object that should be used for reflections.

    Wrapped in ``RealtimePublishingReflectionService`` (Phase 37) before
    being returned — publishes ReflectionGenerated after every
    ``generate()`` with no change to ``ReflectionService`` itself.
    """
    service: Any = RealtimePublishingReflectionService(
        ReflectionService(memory_service, observability_service), realtime_service
    )
    return service
