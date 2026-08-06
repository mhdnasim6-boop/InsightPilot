"""Deterministic, network-free provider for tests and local development."""

import asyncio
from collections.abc import AsyncIterator

from backend.ai.models.provider_info import ModelInfo, ProviderHealth
from backend.ai.models.requests import AIRequest
from backend.ai.models.responses import AIResponse, StreamingChunk, TokenUsage
from backend.ai.providers.base import AIProvider
from backend.ai.streaming.stream import AIStream
from backend.utils.time import utc_now


class MockProvider(AIProvider):
    """Echoes requests back in a deterministic shape — no network calls.

    Used as the default provider in tests and local development, and as
    the reference implementation any real provider must also satisfy.
    """

    provider_name = "mock"

    def __init__(self, default_model: str = "mock-model") -> None:
        self._default_model = default_model

    async def generate(self, request: AIRequest) -> AIResponse:
        """Return a deterministic response derived from the prompt."""
        model = request.model or self._default_model
        content = self._render(model, request.prompt)
        prompt_tokens = len(request.prompt.split())
        completion_tokens = len(content.split())
        return AIResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            finish_reason="stop",
        )

    def stream(self, request: AIRequest) -> AIStream:
        """Simulate streaming by yielding the deterministic response word by word."""
        return AIStream(self._generate_chunks(request))

    async def health_check(self) -> ProviderHealth:
        """Always healthy — there's no external dependency to fail."""
        return ProviderHealth(
            provider=self.provider_name,
            healthy=True,
            message="Mock provider has no external dependency and is always healthy.",
            checked_at=utc_now(),
        )

    async def get_model_info(self, model: str | None = None) -> ModelInfo:
        """Describe the (mock) model with static, well-formed limits."""
        return ModelInfo(
            name=model or self._default_model,
            provider=self.provider_name,
            max_input_tokens=8192,
            max_output_tokens=2048,
            supports_streaming=True,
        )

    def _render(self, model: str, prompt: str) -> str:
        return f"[mock:{model}] {prompt}"

    async def _generate_chunks(self, request: AIRequest) -> AsyncIterator[StreamingChunk]:
        model = request.model or self._default_model
        words = self._render(model, request.prompt).split(" ")
        last_index = len(words) - 1
        for index, word in enumerate(words):
            await asyncio.sleep(0)  # yield control, matching a real async stream
            is_final = index == last_index
            yield StreamingChunk(
                delta=word if index == 0 else f" {word}",
                index=index,
                is_final=is_final,
                finish_reason="stop" if is_final else None,
            )
