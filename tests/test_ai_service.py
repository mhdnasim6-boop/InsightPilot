"""Tests for AIService."""

import asyncio

import pytest

from backend.ai.exceptions.errors import ProviderConfigurationError
from backend.ai.models.requests import AIRequest
from backend.ai.providers.factory import ProviderFactory
from backend.services.ai_service import AIService
from config.settings import Settings


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
    async def scenario() -> None:
        settings = Settings(ai_default_provider="mock", ai_streaming_enabled=True)
        service = AIService(ProviderFactory(settings), settings)

        text = await service.stream(AIRequest(prompt="hello")).collect()

        assert "hello" in text

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
