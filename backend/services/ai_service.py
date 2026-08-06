"""AI generation orchestration.

The only object routers, background jobs, and future LangGraph nodes
should use for AI calls — never a provider or the ``ProviderFactory``
directly. Swapping the default provider, or adding a new one, never
touches a caller of this service.

``observability_service`` is an optional collaborator, mirroring how
``OrchestrationService`` gained an optional ``checkpointer`` in Phase 23:
without one, ``generate()`` behaves exactly as before this phase. With
one, every call records an ``AICallTrace`` — this is the single choke
point every AI call in the system passes through, so it is also the
only place that needs to know tracing exists.
"""

import logging
import time

from backend.ai.exceptions.errors import (
    ProviderConfigurationError,
    ProviderTimeoutError,
)
from backend.ai.models.provider_info import ModelInfo, ProviderHealth
from backend.ai.models.requests import AIRequest
from backend.ai.models.responses import AIResponse
from backend.ai.providers.base import AIProvider
from backend.ai.providers.factory import ProviderFactory
from backend.ai.providers.mock import MockProvider
from backend.ai.streaming.stream import AIStream
from backend.observability.context import current_agent_name, current_trace_id
from backend.observability.models.ai_trace import AICallTrace
from backend.observability.services.cost import estimate_cost
from backend.observability.services.observability_service import ObservabilityService
from backend.utils.time import utc_now
from config.settings import Settings

logger = logging.getLogger(__name__)


class AIService:
    """Receives an ``AIRequest``, resolves a provider, executes it, returns the result."""

    def __init__(
        self,
        provider_factory: ProviderFactory,
        settings: Settings,
        observability_service: ObservabilityService | None = None,
    ) -> None:
        self._provider_factory = provider_factory
        self._settings = settings
        self._observability_service = observability_service

    async def generate(self, request: AIRequest, provider_name: str | None = None) -> AIResponse:
        """Execute a single, non-streamed AI generation.

        If the resolved provider is Ollama and it turns out to be unreachable, falls
        back to the mock provider once rather than failing the request outright —
        callers can detect this via ``response.metadata["fallback_reason"]``. Any
        other provider's failure (e.g. a misconfigured OpenAI key) is raised as-is.
        """
        provider = self._provider_factory.create(provider_name)
        resolved_request = self._apply_defaults(request)

        try:
            return await self._execute(provider, resolved_request)
        except (ProviderTimeoutError, ProviderConfigurationError):
            if provider.provider_name != "ollama":
                raise
            logger.warning("Ollama is unreachable; falling back to the mock provider.")
            fallback_response = await self._execute(
                MockProvider(default_model=self._settings.ai_default_model), resolved_request
            )
            return fallback_response.model_copy(
                update={"metadata": {**fallback_response.metadata, "fallback_reason": "ollama_unreachable"}}
            )

    async def _execute(self, provider: AIProvider, request: AIRequest) -> AIResponse:
        if self._observability_service is None or current_trace_id.get() is None:
            return await provider.generate(request)

        start_time = utc_now()
        start = time.perf_counter()
        response = await provider.generate(request)
        end_time = utc_now()
        self._observability_service.record_ai_call(
            AICallTrace(
                agent_name=current_agent_name.get(),
                provider=response.provider,
                model=response.model,
                tokens=response.usage,
                start_time=start_time,
                end_time=end_time,
                latency_ms=(time.perf_counter() - start) * 1000,
                estimated_cost=estimate_cost(response.provider, response.model, response.usage),
                temperature=request.temperature,
            )
        )
        return response

    def stream(self, request: AIRequest, provider_name: str | None = None) -> AIStream:
        """Execute a streamed AI generation.

        Raises ``ProviderConfigurationError`` if streaming is disabled by configuration.
        """
        if not self._settings.ai_streaming_enabled:
            raise ProviderConfigurationError("Streaming is disabled by configuration.")
        provider = self._provider_factory.create(provider_name)
        return provider.stream(self._apply_defaults(request))

    async def health_check(self, provider_name: str | None = None) -> ProviderHealth:
        """Check whether a provider (or the configured default) is reachable."""
        provider = self._provider_factory.create(provider_name)
        return await provider.health_check()

    async def get_model_info(self, provider_name: str | None = None, model: str | None = None) -> ModelInfo:
        """Describe a model exposed by a provider (or the configured default)."""
        provider = self._provider_factory.create(provider_name)
        return await provider.get_model_info(model)

    def _apply_defaults(self, request: AIRequest) -> AIRequest:
        """Fill unset generation parameters from configured defaults.

        Deliberately leaves ``model`` alone when unset, rather than forcing in
        ``Settings.ai_default_model`` (which is Mock's own default model, not a
        universal one): every provider already falls back to its own configured
        default model (``self._default_model``, built from ``ollama_model``/
        ``openai_model``/``ai_default_model`` respectively — see
        ``backend.ai.providers.factory``) when ``request.model`` is ``None``. Forcing
        a single default here would silently ask, say, Ollama to serve a model named
        "mock-model", which doesn't exist on a real Ollama server.
        """
        return request.model_copy(
            update={
                "temperature": (
                    request.temperature if request.temperature is not None else self._settings.ai_temperature
                ),
                "max_tokens": request.max_tokens if request.max_tokens is not None else self._settings.ai_max_tokens,
            }
        )
