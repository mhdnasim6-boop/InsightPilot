"""Provider-independent streaming abstraction.

Wraps an async sequence of ``StreamingChunk`` objects so callers (a
future FastAPI ``StreamingResponse``, a LangGraph node, a test) iterate
the same way regardless of which provider produced the stream.
"""

from collections.abc import AsyncIterator

from backend.ai.models.responses import StreamingChunk


class AIStream:
    """An async-iterable stream of ``StreamingChunk`` objects from a single generation."""

    def __init__(self, chunks: AsyncIterator[StreamingChunk]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> AsyncIterator[StreamingChunk]:
        return self._chunks

    async def collect(self) -> str:
        """Consume the entire stream and return the concatenated content.

        Useful for tests and any caller that doesn't need incremental
        delivery — it still goes through the same streaming path a real
        consumer would use.
        """
        parts = [chunk.delta async for chunk in self._chunks]
        return "".join(parts)
