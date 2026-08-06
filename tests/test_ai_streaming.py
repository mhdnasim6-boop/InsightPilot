"""Tests for the provider-independent AIStream abstraction."""

import asyncio
from collections.abc import AsyncIterator

from backend.ai.models.responses import StreamingChunk
from backend.ai.streaming.stream import AIStream


async def _three_chunks() -> AsyncIterator[StreamingChunk]:
    yield StreamingChunk(delta="Hello", index=0)
    yield StreamingChunk(delta=", ", index=1)
    yield StreamingChunk(delta="world", index=2, is_final=True, finish_reason="stop")


def test_aiter_yields_chunks_in_order() -> None:
    async def scenario() -> None:
        stream = AIStream(_three_chunks())
        deltas = [chunk.delta async for chunk in stream]
        assert deltas == ["Hello", ", ", "world"]

    asyncio.run(scenario())


def test_collect_concatenates_all_deltas() -> None:
    async def scenario() -> None:
        stream = AIStream(_three_chunks())
        text = await stream.collect()
        assert text == "Hello, world"

    asyncio.run(scenario())
