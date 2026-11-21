"""Cloud provider: OpenAI chat models."""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .base import AIProvider, ProviderUnavailable


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, model: str = "gpt-4o-mini", api_key: str = "", temperature: float = 0.0):
        self.model_name = model
        self.api_key = api_key
        self.temperature = temperature
        self._model: BaseChatModel | None = None

    def get_chat_model(self) -> BaseChatModel:
        if self._model is None:
            if not self.api_key:
                raise ProviderUnavailable("OPENAI_API_KEY is not set")
            from langchain_openai import ChatOpenAI

            self._model = ChatOpenAI(model=self.model_name, api_key=self.api_key, temperature=self.temperature)
        return self._model
