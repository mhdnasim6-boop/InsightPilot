"""Tests for MockProvider — deterministic, network-free, streaming-capable."""

import asyncio

from backend.ai.models.requests import AIRequest
from backend.ai.providers.mock import MockProvider


def test_generate_is_deterministic() -> None:
    async def scenario() -> None:
        provider = MockProvider(default_model="mock-model")
        request = AIRequest(prompt="hello world")

        first = await provider.generate(request)
        second = await provider.generate(request)

        assert first.content == second.content
        assert first.provider == "mock"
        assert first.model == "mock-model"
        assert first.usage.total_tokens == first.usage.prompt_tokens + first.usage.completion_tokens

    asyncio.run(scenario())


def test_generate_uses_requested_model() -> None:
    async def scenario() -> None:
        provider = MockProvider()
        response = await provider.generate(AIRequest(prompt="hi", model="custom-model"))
        assert response.model == "custom-model"
        assert "custom-model" in response.content

    asyncio.run(scenario())


def test_stream_reconstructs_generate_content() -> None:
    async def scenario() -> None:
        provider = MockProvider()
        request = AIRequest(prompt="hello world")

        generated = await provider.generate(request)
        streamed_text = await provider.stream(request).collect()

        assert streamed_text == generated.content

    asyncio.run(scenario())


def test_stream_chunks_have_final_marker() -> None:
    async def scenario() -> None:
        provider = MockProvider()
        chunks = [chunk async for chunk in provider.stream(AIRequest(prompt="a b c"))]

        assert len(chunks) > 1
        assert chunks[-1].is_final is True
        assert all(not chunk.is_final for chunk in chunks[:-1])

    asyncio.run(scenario())


def test_health_check_is_always_healthy() -> None:
    async def scenario() -> None:
        provider = MockProvider()
        health = await provider.health_check()
        assert health.healthy is True
        assert health.provider == "mock"

    asyncio.run(scenario())


def test_get_model_info() -> None:
    async def scenario() -> None:
        provider = MockProvider(default_model="mock-model")
        info = await provider.get_model_info()
        assert info.name == "mock-model"
        assert info.supports_streaming is True

    asyncio.run(scenario())
