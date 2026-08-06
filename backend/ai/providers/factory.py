"""Builds an ``AIProvider`` from configuration.

This is the only place that maps a provider name to a concrete class —
adding a new provider means registering it here, nothing else changes.
"""

from collections.abc import Callable

from backend.ai.exceptions.errors import (
    ProviderConfigurationError,
    ProviderNotFoundError,
)
from backend.ai.providers.base import AIProvider
from backend.ai.providers.detection import ProviderDetector
from backend.ai.providers.mock import MockProvider
from backend.ai.providers.ollama import OllamaProvider
from backend.ai.providers.openai import OpenAIProvider
from config.settings import Settings

_REGISTRY: dict[str, Callable[[Settings], AIProvider]] = {
    "mock": lambda settings: MockProvider(default_model=settings.ai_default_model),
    "ollama": lambda settings: OllamaProvider(
        base_url=settings.ollama_base_url, default_model=settings.ollama_model,
        timeout_seconds=settings.ai_timeout_seconds,
    ),
    "openai": lambda settings: OpenAIProvider(
        api_key=settings.openai_api_key, base_url=settings.openai_base_url, default_model=settings.openai_model,
        timeout_seconds=settings.ai_timeout_seconds,
    ),
}

# Recognized provider names with no implementation yet in this phase.
_PLACEHOLDERS = frozenset({"anthropic", "gemini"})

# "auto" is a recognized meta-value, not a real registry entry — see ProviderDetector.
_META_VALUES = frozenset({"auto"})


class ProviderFactory:
    """Resolves a provider name (or the configured default) to a provider instance."""

    def __init__(self, settings: Settings, detector: ProviderDetector | None = None) -> None:
        self._settings = settings
        self._detector = detector or ProviderDetector()

    def create(self, provider_name: str | None = None) -> AIProvider:
        """Build the requested provider, or the configured default if none is given.

        ``"auto"`` (explicit, or as the configured default) resolves via
        ``ProviderDetector`` to a concrete name first — see that module's own
        docstring for why detection is deliberately synchronous and cached.
        """
        name = (provider_name or self._settings.ai_default_provider).strip().lower()

        if name in _META_VALUES:
            name = self._detector.resolve(self._settings)

        if name in _PLACEHOLDERS:
            raise ProviderConfigurationError(
                f"Provider '{name}' is recognized but not implemented in this phase."
            )

        builder = _REGISTRY.get(name)
        if builder is None:
            raise ProviderNotFoundError(f"Unknown AI provider: '{name}'.")

        return builder(self._settings)

    def available_providers(self) -> list[str]:
        """Return the names of providers that can actually be instantiated today."""
        return sorted(_REGISTRY.keys())
