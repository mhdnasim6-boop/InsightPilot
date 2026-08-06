"""AIPublisher: AICallStarted/AICallCompleted.

Wraps ``AIService`` — ``stream``/``health_check``/``get_model_info`` are
forwarded unchanged via ``__getattr__``; only ``generate()`` (the one
non-streamed call this phase's event pair actually names) is wrapped,
mirroring ``TracingTool``'s before/after/on-exception shape. Wired into
``get_ai_service()`` (``backend.dependencies.ai``), the single provider
every tool and agent that calls AI already depends on.
"""

from typing import Any

from backend.ai.models.requests import AIRequest
from backend.ai.models.responses import AIResponse
from backend.observability.context import current_agent_name, current_trace_id
from backend.realtime.events.event import Event
from backend.realtime.events.event_type import EventType
from backend.realtime.services.realtime_service import RealtimeService
from backend.services.ai_service import AIService


class RealtimePublishingAIService:
    """Wraps a real AIService, publishing AICall* events around ``generate()``."""

    def __init__(self, inner: AIService, realtime_service: RealtimeService) -> None:
        self._inner = inner
        self._realtime_service = realtime_service

    async def generate(self, request: AIRequest, provider_name: str | None = None) -> AIResponse:
        trace_id = current_trace_id.get()
        agent_name = current_agent_name.get()
        self._realtime_service.publish(
            Event(event_type=EventType.AI_CALL_STARTED, trace_id=trace_id, agent_name=agent_name)
        )
        response = await self._inner.generate(request, provider_name)
        self._realtime_service.publish(
            Event(
                event_type=EventType.AI_CALL_COMPLETED,
                trace_id=trace_id,
                agent_name=agent_name,
                data={"provider": response.provider, "model": response.model, "tokens": response.usage.model_dump()},
            )
        )
        return response

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
