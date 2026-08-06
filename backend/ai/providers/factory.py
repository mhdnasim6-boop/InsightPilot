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
from backend.ai.providers.mock import MockProvider
from config.settings import Settings

_REGISTRY: dict[str, Callable[[Settings], AIProvider]] = {
    "mock": lambda settings: MockProvider(default_model=settings.ai_default_model),
}

# Recognized provider names with no implementation yet in this phase.
_PLACEHOLDERS = frozenset({"openai", "anthropic", "ollama", "gemini"})


class ProviderFactory:
    """Resolves a provider name (or the configured default) to a provider instance."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, provider_name: str | None = None) -> AIProvider:
        """Build the requested provider, or the configured default if none is given."""
        name = (provider_name or self._settings.ai_default_provider).strip().lower()

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
