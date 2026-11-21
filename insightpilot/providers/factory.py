"""Chooses the AIProvider from configuration. This is the only place that knows the vendors."""
from __future__ import annotations

from ..config import Settings, get_settings
from .base import AIProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider

PROVIDER_NAMES = ("ollama", "openai")


def get_provider(name: str | None = None, settings: Settings | None = None) -> AIProvider:
    s = settings or get_settings()
    choice = (name or s.llm_provider).strip().lower()
    if choice == "ollama":
        return OllamaProvider(model=s.ollama_model, base_url=s.ollama_base_url, num_ctx=s.ollama_num_ctx)
    if choice == "openai":
        return OpenAIProvider(model=s.openai_model, api_key=s.openai_api_key)
    raise ValueError(f"Unknown LLM_PROVIDER '{choice}'. Use one of: {', '.join(PROVIDER_NAMES)}")
