"""OllamaProvider: real generation against a locally-running Ollama server.

Uses Ollama's own ``/api/chat`` endpoint (not ``/api/generate``) specifically
because it takes a ``messages`` array with distinct ``system``/``user`` roles —
matching ``AIRequest.system_prompt``/``AIRequest.prompt`` exactly, so the
model is never asked to repeat its own system instructions back (the same
structural fix this phase applies to prompt construction generally).

Every network failure is translated into this codebase's own ``AIError``
hierarchy (``ProviderTimeoutError``/``ProviderConfigurationError``) before it
ever leaves this module — a caller never sees a raw ``httpx`` exception, and
the existing global exception-handler middleware turns those into the
unified API error envelope automatically, the same as any other
``InsightPilotError``.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from backend.ai.exceptions.errors import (
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


class OllamaProvider(AIProvider):
    """Generates against a real Ollama server's ``/api/chat`` endpoint."""

    provider_name = "ollama"

    def __init__(
        self,
        base_url: str,
        default_model: str,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._timeout_seconds = timeout_seconds
        # Only ever set by tests, to inject a synchronous httpx.MockTransport — same
        # convention as frontend.api.client.APIClient. None in production, which
        # leaves httpx.AsyncClient's own default (real network) transport untouched.
        self._transport = transport

    async def generate(self, request: AIRequest) -> AIResponse:
        model = request.model or self._default_model
        payload = {"model": model, "messages": self._messages(request), "stream": False, **self._options(request)}

        data = await self._post("/api/chat", payload)
        content = str(data.get("message", {}).get("content", ""))
        prompt_tokens = int(data.get("prompt_eval_count", 0))
        completion_tokens = int(data.get("eval_count", 0))
        return AIResponse(
            content=content,
            model=model,
            provider=self.provider_name,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            finish_reason=data.get("done_reason") or "stop",
        )

    def stream(self, request: AIRequest) -> AIStream:
        return AIStream(self._generate_chunks(request))

    async def health_check(self) -> ProviderHealth:
        try:
            async with httpx.AsyncClient(timeout=_HEALTH_CHECK_TIMEOUT_SECONDS, transport=self._transport) as client:
                response = await client.get(f"{self._base_url}/api/tags")
            healthy = response.status_code == 200
            message = "Ollama is reachable." if healthy else f"Ollama responded with status {response.status_code}."
        except httpx.HTTPError as exc:
            healthy = False
            message = f"Could not reach Ollama at {self._base_url}: {exc}"
        return ProviderHealth(provider=self.provider_name, healthy=healthy, message=message, checked_at=utc_now())

    async def get_model_info(self, model: str | None = None) -> ModelInfo:
        """Describe the model by name only — deliberately doesn't call Ollama's own
        ``/api/show`` (a heavy response carrying the full model license/template text)
        just to answer this. Token limits are honestly reported as unknown rather than
        guessed."""
        return ModelInfo(
            name=model or self._default_model, provider=self.provider_name,
            max_input_tokens=None, max_output_tokens=None, supports_streaming=True,
        )

    def _messages(self, request: AIRequest) -> list[dict[str, str]]:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        return messages

    def _options(self, request: AIRequest) -> dict[str, dict[str, float | int]]:
        options: dict[str, float | int] = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens
        return {"options": options} if options else {}

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, transport=self._transport) as client:
                response = await client.post(f"{self._base_url}{path}", json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Ollama request timed out after {self._timeout_seconds}s.") from exc
        except httpx.HTTPError as exc:
            raise ProviderConfigurationError(f"Could not reach Ollama at {self._base_url}: {exc}") from exc
        result: dict[str, Any] = response.json()
        return result

    async def _generate_chunks(self, request: AIRequest) -> AsyncIterator[StreamingChunk]:
        model = request.model or self._default_model
        payload = {"model": model, "messages": self._messages(request), "stream": True, **self._options(request)}
        index = 0
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, transport=self._transport) as client, client.stream(
                "POST", f"{self._base_url}/api/chat", json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    chunk_data = json.loads(line)
                    is_final = bool(chunk_data.get("done", False))
                    delta = str(chunk_data.get("message", {}).get("content", ""))
                    yield StreamingChunk(
                        delta=delta, index=index, is_final=is_final,
                        finish_reason=chunk_data.get("done_reason") if is_final else None,
                    )
                    index += 1
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"Ollama request timed out after {self._timeout_seconds}s.") from exc
        except httpx.HTTPError as exc:
            raise ProviderConfigurationError(f"Could not reach Ollama at {self._base_url}: {exc}") from exc
