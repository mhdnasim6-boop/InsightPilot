"""Tests for ProviderFactory."""

import pytest

from backend.ai.exceptions.errors import (
    ProviderConfigurationError,
    ProviderNotFoundError,
)
from backend.ai.providers.factory import ProviderFactory
from backend.ai.providers.mock import MockProvider
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


def test_create_placeholder_provider_raises_configuration_error() -> None:
    factory = ProviderFactory(Settings())
    with pytest.raises(ProviderConfigurationError):
        factory.create("openai")


def test_available_providers_lists_mock() -> None:
    factory = ProviderFactory(Settings())
    assert "mock" in factory.available_providers()
