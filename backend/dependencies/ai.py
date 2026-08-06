"""AI infrastructure providers: prompt manager, provider factory, AI service."""

from functools import lru_cache
from typing import Any

from fastapi import Depends

from backend.ai.prompts.manager import PromptManager
from backend.ai.providers.factory import ProviderFactory
from backend.dependencies.observability import get_observability_service
from backend.dependencies.realtime import get_realtime_service
from backend.observability.services.observability_service import ObservabilityService
from backend.realtime.publishers.ai_publisher import RealtimePublishingAIService
from backend.realtime.services.realtime_service import RealtimeService
from backend.services.ai_service import AIService
from config.settings import Settings, get_settings


@lru_cache
def get_prompt_manager() -> PromptManager:
    """Return the process-wide prompt manager singleton.

    Cached like the repositories: prompt registrations must persist
    across requests within the process.
    """
    return PromptManager()


def get_provider_factory(settings: Settings = Depends(get_settings)) -> ProviderFactory:
    """Provide a ``ProviderFactory`` bound to the current settings."""
    return ProviderFactory(settings)


def get_ai_service(
    provider_factory: ProviderFactory = Depends(get_provider_factory),
    settings: Settings = Depends(get_settings),
    observability_service: ObservabilityService = Depends(get_observability_service),
    realtime_service: RealtimeService = Depends(get_realtime_service),
) -> AIService:
    """Provide the ``AIService`` — the only object that should be used for AI calls.

    Wrapped in ``RealtimePublishingAIService`` (Phase 37) before being
    returned — publishes AICallStarted/AICallCompleted around every
    ``generate()`` call with no change to ``AIService`` itself, the same
    "wrap at the single source every consumer already depends on" pattern
    used throughout this phase.
    """
    service: Any = RealtimePublishingAIService(
        AIService(provider_factory, settings, observability_service), realtime_service
    )
    return service
