"""Tests for OpenAIProvider.

Each test injects a synchronous ``httpx.MockTransport`` (the same technique
``tests/test_frontend_api_client.py`` uses for ``APIClient``) so these run
without hitting the real OpenAI API or needing a real API key.
"""

import asyncio
import json

import httpx
import pytest

from backend.ai.exceptions.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderTimeoutError,
)
from backend.ai.models.requests import AIRequest
from backend.ai.providers.openai import OpenAIProvider

_BASE_URL = "https://api.openai.com/v1"


def _provider(handler: httpx.MockTransport, api_key: str = "sk-test-key") -> OpenAIProvider:
    return OpenAIProvider(
        api_key=api_key, base_url=_BASE_URL, default_model="gpt-4o-mini", transport=handler
    )


def test_constructing_without_an_api_key_raises_configuration_error_eagerly() -> None:
    with pytest.raises(ProviderConfigurationError):
        OpenAIProvider(api_key=None, base_url=_BASE_URL, default_model="gpt-4o-mini")


def test_constructing_with_an_empty_api_key_raises_configuration_error_eagerly() -> None:
    with pytest.raises(ProviderConfigurationError):
        OpenAIProvider(api_key="", base_url=_BASE_URL, default_model="gpt-4o-mini")


def test_generate_returns_the_message_content_and_token_usage() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer sk-test-key"
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["messages"] == [{"role": "user", "content": "2+2?"}]
        return httpx.Response(
            200,
            json={
                "model": "gpt-4o-mini",
                "choices": [{"message": {"content": "4"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
            },
        )

    provider = _provider(httpx.MockTransport(handle))
    response = asyncio.run(provider.generate(AIRequest(prompt="2+2?")))

    assert response.content == "4"
    assert response.provider == "openai"
    assert response.model == "gpt-4o-mini"
    assert response.usage.prompt_tokens == 5
    assert response.usage.total_tokens == 6
    assert response.finish_reason == "stop"


def test_generate_sends_the_system_prompt_as_a_separate_message() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["messages"] == [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hi"},
        ]
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Hello!"}}], "usage": {}}
        )

    provider = _provider(httpx.MockTransport(handle))
    response = asyncio.run(
        provider.generate(AIRequest(system_prompt="You are a helpful assistant.", prompt="Hi"))
    )

    assert response.content == "Hello!"


def test_generate_raises_authentication_error_on_401() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid API key."}})

    provider = _provider(httpx.MockTransport(handle))
    with pytest.raises(ProviderAuthenticationError):
        asyncio.run(provider.generate(AIRequest(prompt="hi")))


def test_generate_wraps_a_timeout_as_provider_timeout_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    provider = _provider(httpx.MockTransport(handle))
    with pytest.raises(ProviderTimeoutError):
        asyncio.run(provider.generate(AIRequest(prompt="hi")))


def test_generate_wraps_a_non_401_http_error_as_provider_configuration_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"message": "Internal error."}})

    provider = _provider(httpx.MockTransport(handle))
    with pytest.raises(ProviderConfigurationError):
        asyncio.run(provider.generate(AIRequest(prompt="hi")))


def test_stream_yields_chunks_from_sse_lines() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        events = [
            f"data: {json.dumps({'choices': [{'delta': {'content': '1'}, 'finish_reason': None}]})}",
            f"data: {json.dumps({'choices': [{'delta': {'content': ', 2'}, 'finish_reason': None}]})}",
            f"data: {json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}]})}",
            "data: [DONE]",
        ]
        return httpx.Response(200, content=("\n".join(events) + "\n").encode())

    provider = _provider(httpx.MockTransport(handle))

    async def scenario() -> str:
        return await provider.stream(AIRequest(prompt="count to 2")).collect()

    assert asyncio.run(scenario()) == "1, 2"


async def _health_check(provider: OpenAIProvider) -> tuple[bool, str]:
    health = await provider.health_check()
    return health.healthy, health.message


def test_health_check_reports_healthy_on_a_200_response() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(200, json={"data": []})

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


def test_get_model_info_reports_known_context_window_for_a_recognized_model() -> None:
    provider = OpenAIProvider(api_key="sk-test-key", base_url=_BASE_URL, default_model="gpt-4o-mini")

    async def scenario() -> None:
        info = await provider.get_model_info()
        assert info.name == "gpt-4o-mini"
        assert info.provider == "openai"
        assert info.max_input_tokens == 128_000
        assert info.supports_streaming is True

    asyncio.run(scenario())


def test_get_model_info_reports_honest_unknown_for_an_unrecognized_model() -> None:
    provider = OpenAIProvider(api_key="sk-test-key", base_url=_BASE_URL, default_model="some-future-model")

    async def scenario() -> None:
        info = await provider.get_model_info()
        assert info.max_input_tokens is None

    asyncio.run(scenario())
