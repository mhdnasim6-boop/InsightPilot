"""Tests for ProviderFactory."""

import pytest

from backend.ai.exceptions.errors import (
    ProviderConfigurationError,
    ProviderNotFoundError,
)
from backend.ai.providers.factory import ProviderFactory
from backend.ai.providers.mock import MockProvider
from backend.ai.providers.ollama import OllamaProvider
from backend.ai.providers.openai import OpenAIProvider
from config.settings import Settings


def test_create_returns_mock_provider_by_default() -> None:
    factory = ProviderFactory(Settings(ai_default_provider="mock"))
    provider = factory.create()
    assert isinstance(provider, MockProvider)


def test_create_with_explicit_name() -> None:
    factory = ProviderFactory(Settings())
    provider = factory.create("mock")
    assert isinstance(provider, MockProvider)


def test_create_unknown_provider_raises_not_found() -> None:
    factory = ProviderFactory(Settings())
    with pytest.raises(ProviderNotFoundError):
        factory.create("not-a-real-provider")


def test_create_ollama_returns_ollama_provider() -> None:
    factory = ProviderFactory(Settings(ollama_base_url="http://127.0.0.1:11434", ollama_model="qwen2.5:3b"))
    provider = factory.create("ollama")
    assert isinstance(provider, OllamaProvider)


def test_create_openai_returns_openai_provider() -> None:
    factory = ProviderFactory(Settings(openai_api_key="sk-test-key"))
    provider = factory.create("openai")
    assert isinstance(provider, OpenAIProvider)


def test_create_openai_without_api_key_raises_configuration_error() -> None:
    """OpenAI is a real, implemented provider now - it only fails when
    misconfigured (no API key), never because it's unimplemented."""
    factory = ProviderFactory(Settings(openai_api_key=None))
    with pytest.raises(ProviderConfigurationError):
        factory.create("openai")


def test_create_still_placeholder_provider_raises_configuration_error() -> None:
    factory = ProviderFactory(Settings())
    with pytest.raises(ProviderConfigurationError):
        factory.create("anthropic")


def test_available_providers_lists_every_real_provider() -> None:
    factory = ProviderFactory(Settings())
    assert factory.available_providers() == ["mock", "ollama", "openai"]
