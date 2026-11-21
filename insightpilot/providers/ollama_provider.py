"""Local provider: Ollama serving Qwen2.5:3B (runs on a laptop, no API cost, data stays local)."""
from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel

from .base import AIProvider


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self, model: str = "qwen2.5:3b", base_url: str = "http://localhost:11434",
                 num_ctx: int = 8192, temperature: float = 0.0):
        self.model_name = model
        self.base_url = base_url
        self.num_ctx = num_ctx
        self.temperature = temperature
        self._model: BaseChatModel | None = None

    def get_chat_model(self) -> BaseChatModel:
        if self._model is None:
            from langchain_ollama import ChatOllama

            self._model = ChatOllama(
                model=self.model_name,
                base_url=self.base_url,
                num_ctx=self.num_ctx,        # Ollama's default context is small; raise it explicitly
                temperature=self.temperature,  # deterministic output suits routing and SQL
            )
        return self._model

    def _invoke_structured(self, messages, schema) -> Any:
        # Ollama constrains decoding to the JSON schema, which helps a 3B model a lot.
        return self.get_chat_model().with_structured_output(schema, method="json_schema").invoke(messages)
