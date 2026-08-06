"""Tests for AIService."""

import asyncio

import pytest

from backend.ai.exceptions.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderTimeoutError,
)
from backend.ai.models.provider_info import ModelInfo, ProviderHealth
from backend.ai.models.requests import AIRequest
from backend.ai.models.responses import AIResponse
from backend.ai.providers.base import AIProvider
from backend.ai.providers.factory import ProviderFactory
from backend.ai.streaming.stream import AIStream
from backend.services.ai_service import AIService
from config.settings import Settings


class _AlwaysFailingProvider(AIProvider):
    """A provider that always raises a given error - used to simulate a
    provider that is unreachable (Ollama) or misconfigured (OpenAI)."""

    def __init__(self, provider_name: str, error: Exception) -> None:
        self.provider_name = provider_name
        self._error = error

    async def generate(self, request: AIRequest) -> AIResponse:
        raise self._error

    def stream(self, request: AIRequest) -> AIStream:
        raise self._error

    async def health_check(self) -> ProviderHealth:
        raise self._error

    async def get_model_info(self, model: str | None = None) -> ModelInfo:
        raise self._error


class _SingleProviderFactory:
    """A ``ProviderFactory`` stand-in that always returns one fixed provider."""

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    def create(self, provider_name: str | None = None) -> AIProvider:
        return self._provider


def test_generate_applies_configured_defaults() -> None:
    async def scenario() -> None:
        settings = Settings(
            ai_default_provider="mock",
            ai_default_model="configured-model",
            ai_temperature=0.3,
            ai_max_tokens=256,
        )
        service = AIService(ProviderFactory(settings), settings)

        response = await service.generate(AIRequest(prompt="hi"))

        assert response.model == "configured-model"

    asyncio.run(scenario())


def test_generate_respects_explicit_overrides() -> None:
    async def scenario() -> None:
        settings = Settings(ai_default_provider="mock", ai_default_model="configured-model")
        service = AIService(ProviderFactory(settings), settings)

        response = await service.generate(AIRequest(prompt="hi", model="explicit-model"))

        assert response.model == "explicit-model"

    asyncio.run(scenario())


def test_stream_disabled_raises_configuration_error() -> None:
    settings = Settings(ai_default_provider="mock", ai_streaming_enabled=False)
    service = AIService(ProviderFactory(settings), settings)

    with pytest.raises(ProviderConfigurationError):
        service.stream(AIRequest(prompt="hi"))


def test_stream_enabled_returns_stream() -> None:
    """MockProvider never echoes the prompt (see backend/ai/providers/mock.py), so this
    only proves streaming reconstructs the same text generate() would return, word by
    word - not that "hello" itself appears."""

    async def scenario() -> None:
        settings = Settings(ai_default_provider="mock", ai_streaming_enabled=True)
        service = AIService(ProviderFactory(settings), settings)

        streamed_text = await service.stream(AIRequest(prompt="hello")).collect()
        generated = await service.generate(AIRequest(prompt="hello"))

        assert streamed_text == generated.content

    asyncio.run(scenario())


def test_health_check_delegates_to_provider() -> None:
    async def scenario() -> None:
        settings = Settings(ai_default_provider="mock")
        service = AIService(ProviderFactory(settings), settings)

        health = await service.health_check()

        assert health.healthy is True

    asyncio.run(scenario())


def test_get_model_info_delegates_to_provider() -> None:
    async def scenario() -> None:
        settings = Settings(ai_default_provider="mock", ai_default_model="configured-model")
        service = AIService(ProviderFactory(settings), settings)

        info = await service.get_model_info()

        assert info.name == "configured-model"

    asyncio.run(scenario())


def test_generate_falls_back_to_mock_when_ollama_is_unreachable() -> None:
    """A connectivity-class failure from the Ollama provider specifically must not
    fail the request - it should retry against Mock and tag the response so callers
    (the Chat page) can show a "falling back to development mode" banner."""

    async def scenario() -> None:
        settings = Settings(ai_default_provider="mock", ai_default_model="configured-model")
        failing_provider = _AlwaysFailingProvider("ollama", ProviderTimeoutError("Ollama timed out."))
        service = AIService(_SingleProviderFactory(failing_provider), settings)  # type: ignore[arg-type]

        response = await service.generate(AIRequest(prompt="hello"))

        assert response.provider == "mock"
        assert response.metadata["fallback_reason"] == "ollama_unreachable"

    asyncio.run(scenario())


def test_generate_does_not_fall_back_for_non_ollama_provider_failures() -> None:
    """OpenAI (or any other provider) failing must surface as a real error - never
    silently substituted with a mock response."""

    async def scenario() -> None:
        settings = Settings(ai_default_provider="mock")
        failing_provider = _AlwaysFailingProvider("openai", ProviderAuthenticationError("Invalid API key."))
        service = AIService(_SingleProviderFactory(failing_provider), settings)  # type: ignore[arg-type]

        with pytest.raises(ProviderAuthenticationError):
            await service.generate(AIRequest(prompt="hello"))

    asyncio.run(scenario())
