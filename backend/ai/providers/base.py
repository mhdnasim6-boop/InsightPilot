"""Abstract provider interface every LLM backend must implement.

This is the one seam between InsightPilot and any LLM SDK. Callers —
``AIService`` today, LangGraph nodes or another orchestration framework
tomorrow — depend only on this interface and the provider-independent
models in ``backend.ai.models``. No provider-specific type ever crosses it.
"""

from abc import ABC, abstractmethod

from backend.ai.models.provider_info import ModelInfo, ProviderHealth
from backend.ai.models.requests import AIRequest
from backend.ai.models.responses import AIResponse
from backend.ai.streaming.stream import AIStream


class AIProvider(ABC):
    """Contract every LLM provider (mock or real) must satisfy."""

    provider_name: str

    @abstractmethod
    async def generate(self, request: AIRequest) -> AIResponse:
        """Run a single, non-streamed generation and return the full response."""

    @abstractmethod
    def stream(self, request: AIRequest) -> AIStream:
        """Run a streamed generation, returning an ``AIStream`` of chunks."""

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Report whether this provider is currently reachable and usable."""

    @abstractmethod
    async def get_model_info(self, model: str | None = None) -> ModelInfo:
        """Describe a model this provider exposes (or its default model)."""
