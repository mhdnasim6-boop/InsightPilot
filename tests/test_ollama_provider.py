"""Tests for OllamaProvider.

Each test injects a synchronous ``httpx.MockTransport`` (the same technique
``tests/test_frontend_api_client.py`` uses for ``APIClient``) so these run
without a real Ollama server. One additional test is a real, network-touching
smoke check against a genuinely running local Ollama server — guarded so it
self-skips wherever one isn't reachable (a fresh checkout, most CI runners).
"""

import asyncio
import json

import httpx
import pytest

from backend.ai.exceptions.errors import (
    ProviderConfigurationError,
    ProviderTimeoutError,
)
from backend.ai.models.requests import AIRequest
from backend.ai.providers.ollama import OllamaProvider

_BASE_URL = "http://127.0.0.1:11434"


def _provider(handler: httpx.MockTransport) -> OllamaProvider:
    return OllamaProvider(base_url=_BASE_URL, default_model="qwen2.5:3b", transport=handler)


def test_generate_returns_the_message_content_and_token_usage() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["messages"] == [{"role": "user", "content": "2+2?"}]
        return httpx.Response(
            200,
            json={
                "message": {"content": "4"},
                "prompt_eval_count": 5,
                "eval_count": 1,
                "done_reason": "stop",
            },
        )

    provider = _provider(httpx.MockTransport(handle))
    response = asyncio.run(provider.generate(AIRequest(prompt="2+2?")))

    assert response.content == "4"
    assert response.provider == "ollama"
    assert response.model == "qwen2.5:3b"
    assert response.usage.prompt_tokens == 5
    assert response.usage.completion_tokens == 1
    assert response.finish_reason == "stop"


def test_generate_sends_the_system_prompt_as_a_separate_message() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["messages"] == [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hi"},
        ]
        return httpx.Response(200, json={"message": {"content": "Hello!"}})

    provider = _provider(httpx.MockTransport(handle))
    response = asyncio.run(
        provider.generate(AIRequest(system_prompt="You are a helpful assistant.", prompt="Hi"))
    )

    assert response.content == "Hello!"


def test_generate_uses_the_requested_model_over_the_default() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "llama3"
        return httpx.Response(200, json={"message": {"content": "ok"}})

    provider = _provider(httpx.MockTransport(handle))
    response = asyncio.run(provider.generate(AIRequest(prompt="hi", model="llama3")))

    assert response.model == "llama3"


def test_generate_wraps_a_timeout_as_provider_timeout_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    provider = _provider(httpx.MockTransport(handle))
    with pytest.raises(ProviderTimeoutError):
        asyncio.run(provider.generate(AIRequest(prompt="hi")))


def test_generate_wraps_a_connection_error_as_provider_configuration_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    provider = _provider(httpx.MockTransport(handle))
    with pytest.raises(ProviderConfigurationError):
        asyncio.run(provider.generate(AIRequest(prompt="hi")))


def test_stream_yields_chunks_from_ndjson_lines() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        lines = [
            json.dumps({"message": {"content": "1"}, "done": False}),
            json.dumps({"message": {"content": ", 2"}, "done": False}),
            json.dumps({"message": {"content": ""}, "done": True, "done_reason": "stop"}),
        ]
        return httpx.Response(200, content="\n".join(lines).encode())

    provider = _provider(httpx.MockTransport(handle))

    async def scenario() -> str:
        return await provider.stream(AIRequest(prompt="count to 2")).collect()

    assert asyncio.run(scenario()) == "1, 2"


async def _health_check(provider: OllamaProvider) -> tuple[bool, str]:
    health = await provider.health_check()
    return health.healthy, health.message


def test_health_check_reports_healthy_on_a_200_response() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": []})

    provider = _provider(httpx.MockTransport(handle))
    healthy, message = asyncio.run(_health_check(provider))

    assert healthy is True
    assert "reachable" in message.lower()


def test_health_check_reports_unhealthy_when_unreachable() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    provider = _provider(httpx.MockTransport(handle))
    healthy, message = asyncio.run(_health_check(provider))

    assert healthy is False
    assert "could not reach" in message.lower()


def test_get_model_info_reports_honest_unknown_token_limits() -> None:
    provider = OllamaProvider(base_url=_BASE_URL, default_model="qwen2.5:3b")

    async def scenario() -> None:
        info = await provider.get_model_info()
        assert info.name == "qwen2.5:3b"
        assert info.provider == "ollama"
        assert info.max_input_tokens is None
        assert info.supports_streaming is True

    asyncio.run(scenario())


def _real_ollama_is_reachable() -> bool:
    try:
        return httpx.get(f"{_BASE_URL}/api/tags", timeout=1.0).status_code == 200
    except httpx.HTTPError:
        return False


@pytest.mark.skipif(not _real_ollama_is_reachable(), reason="No real Ollama server reachable at 127.0.0.1:11434.")
def test_generate_against_a_real_local_ollama_server() -> None:
    """Not mocked - proves the request/response shape actually matches a real
    Ollama server, not just this test file's own assumptions about its API."""
    provider = OllamaProvider(base_url=_BASE_URL, default_model="qwen2.5:3b")

    response = asyncio.run(provider.generate(AIRequest(prompt="Reply with exactly the digit 4 and nothing else.")))

    assert response.content.strip() != ""
    assert response.provider == "ollama"
