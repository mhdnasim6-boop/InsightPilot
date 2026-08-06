"""Adaptive planning providers: the top-level AdaptivePlanningService.

Cached, mirroring ``backend.dependencies.reflection``'s own reasoning:
every one of ``AdaptivePlanningService``'s own dependencies here is
itself an already-cached singleton (``MemoryService``,
``ReflectionService``, ``ObservabilityService``) — nothing varies in
identity between requests. Deliberately does *not* depend on
``CollaborationService`` — see
``backend.adaptive.analyzers.collaboration_patterns``'s own docstring
for why that would be a real circular dependency once ``PlannerService``
(below) depends on this provider.
"""

from functools import lru_cache

from fastapi import Depends

from backend.adaptive.services.adaptive_planning_service import AdaptivePlanningService
from backend.dependencies.memory import get_memory_service
from backend.dependencies.observability import get_observability_service
from backend.dependencies.reflection import get_reflection_service
from backend.memory.services.memory_service import MemoryService
from backend.observability.services.observability_service import ObservabilityService
from backend.reflection.services.reflection_service import ReflectionService


@lru_cache
def get_adaptive_planning_service(
    memory_service: MemoryService = Depends(get_memory_service),
    reflection_service: ReflectionService = Depends(get_reflection_service),
    observability_service: ObservabilityService = Depends(get_observability_service),
) -> AdaptivePlanningService:
    """Provide the AdaptivePlanningService — the only object that should be used for adaptive planning."""
    return AdaptivePlanningService(memory_service, reflection_service, observability_service)
