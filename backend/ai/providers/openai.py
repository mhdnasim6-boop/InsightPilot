"""OpenAIProvider: real generation against the OpenAI API (or an OpenAI-compatible
endpoint — ``base_url`` is configurable specifically so this also works against a
compatible local/self-hosted server).

Same ``system_prompt``/``prompt`` -> distinct ``system``/``user`` messages shape
as ``OllamaProvider`` — the two real providers share the same request-building
discipline, just against a different wire format. Every network/auth failure is
translated into this codebase's own ``AIError`` hierarchy before it ever leaves
this module.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from backend.ai.exceptions.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderTimeoutError,
)
from backend.ai.models.provider_info import ModelInfo, ProviderHealth
from backend.ai.models.requests import AIRequest
from backend.ai.models.responses import AIResponse, StreamingChunk, TokenUsage
from backend.ai.providers.base import AIProvider
from backend.ai.streaming.stream import AIStream
from backend.utils.time import utc_now

_HEALTH_CHECK_TIMEOUT_SECONDS = 5.0

# Known context windows for a few common models — a small, honest convenience,
# not an attempt at a complete catalog. Unrecognized models report None (unknown)
# rather than a guessed number.
_KNOWN_MAX_INPUT_TOKENS: dict[str, int] = {
    "gpt-4o": 128_000, "gpt-4o-mini": 128_000, "gpt-4-turbo": 128_000, "gpt-3.5-turbo": 16_385,
}


class OpenAIProvider(AIProvider):
    """Generates against OpenAI's (or an OpenAI-compatible) ``/chat/completions`` endpoint."""

    provider_name = "openai"

    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        default_model: str,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ProviderConfigurationError("OpenAI provider requires OPENAI_API_KEY to be configured.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._timeout_seconds = timeout_seconds
        # Only ever set by tests, to inject a synchronous httpx.MockTransport — same
        # convention as frontend.api.client.APIClient and OllamaProvider.
        self._transport = transport

    async def generate(self, request: AIRequest) -> AIResponse:
        model = request.model or self._default_model
        payload = {"model": model, "messages": self._messages(request), "stream": False, **self._sampling(request)}

        data = await self._post("/chat/completions", payload)
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return AIResponse(
            content=str(choice["message"]["content"] or ""),
            model=data.get("model", model),
            provider=self.provider_name,
            usage=TokenUsage(
                prompt_tokens=int(usage.get("prompt_tokens", 0)), completion_tokens=int(usage.get("completion_tokens", 0)),
                total_tokens=int(usage.get("total_tokens", 0)),
            ),
            finish_reason=choice.get("finish_reason") or "stop",
        )

    def stream(self, request: AIRequest) -> AIStream:
        return AIStream(self._generate_chunks(request))

    async def health_check(self) -> ProviderHealth:
        try:
            async with httpx.AsyncClient(timeout=_HEALTH_CHECK_TIMEOUT_SECONDS, transport=self._transport) as client:
                response = await client.get(f"{self._base_url}/models", headers=self._headers())
            healthy = response.status_code == 200
            message = "OpenAI is reachable." if healthy else f"OpenAI responded with status {response.status_code}."
        except httpx.HTTPError as exc:
            healthy = False
            message = f"Could not reach OpenAI at {self._base_url}: {exc}"
        return ProviderHealth(provider=self.provider_name, healthy=healthy, message=message, checked_at=utc_now())

    async def get_model_info(self, model: str | None = None) -> ModelInfo:
        name = model or self._default_model
        return ModelInfo(
            name=name, provider=self.provider_name, max_input_tokens=_KNOWN_MAX_INPUT_TOKENS.get(name),
            max_output_tokens=None, supports_streaming=True,
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _messages(self, request: AIRequest) -> list[dict[str, str]]:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        return messages

    def _sampling(self, request: AIRequest) -> dict[str, float | int]:
        sampling: dict[str, float | int] = {}
        if request.temperature is not None:
            sampling["temperature"] = request.temperature
        if request.max_tokens is not None:
            sampling["max_tokens"] = request.max_tokens
        return sampling

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, transport=self._transport) as client:
                response = await client.post(f"{self._base_url}{path}", json=payload, headers=self._headers())
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"OpenAI request timed out after {self._timeout_seconds}s.") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise ProviderAuthenticationError("OpenAI rejected the configured API key.") from exc
            raise ProviderConfigurationError(f"OpenAI request failed: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderConfigurationError(f"Could not reach OpenAI at {self._base_url}: {exc}") from exc
        result: dict[str, Any] = response.json()
        return result

    async def _generate_chunks(self, request: AIRequest) -> AsyncIterator[StreamingChunk]:
        model = request.model or self._default_model
        payload = {"model": model, "messages": self._messages(request), "stream": True, **self._sampling(request)}
        index = 0
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, transport=self._transport) as client, client.stream(
                "POST", f"{self._base_url}/chat/completions", json=payload, headers=self._headers()
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line.removeprefix("data: ").strip()
                    if raw == "[DONE]":
                        break
                    chunk_data = json.loads(raw)
                    delta_content = str(chunk_data["choices"][0]["delta"].get("content") or "")
                    finish_reason = chunk_data["choices"][0].get("finish_reason")
                    is_final = finish_reason is not None
                    yield StreamingChunk(delta=delta_content, index=index, is_final=is_final, finish_reason=finish_reason)
                    index += 1
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"OpenAI request timed out after {self._timeout_seconds}s.") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise ProviderAuthenticationError("OpenAI rejected the configured API key.") from exc
            raise ProviderConfigurationError(f"OpenAI request failed: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderConfigurationError(f"Could not reach OpenAI at {self._base_url}: {exc}") from exc
