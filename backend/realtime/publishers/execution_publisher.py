"""ExecutionPublisher: StepStarted/Completed/Failed + AgentStarted/Completed/Failed.

Wraps one ``AgentService`` (the exact structural ``Protocol`` defined by
``backend.execution.dispatcher.node_dispatcher.AgentService`` — every
real agent service already satisfies it) exactly the way ``TracingTool``
wraps a ``Tool``: publish "started" before delegating, "completed"/"failed"
after. Wired into ``get_node_dispatcher()`` (``backend.dependencies.execution``)
around each of the six real agent services *before* they're registered
into ``NodeDispatcher`` — the single choke point every step of the real,
parallel ``DAGScheduler`` dispatches through, so this is genuine,
per-step, real-time visibility with zero changes to ``NodeDispatcher``,
``DAGScheduler``, or any agent service itself.
"""

from typing import Any

from backend.execution.dispatcher.node_dispatcher import AgentService
from backend.observability.context import current_trace_id
from backend.planning.models.step import ExecutionStep
from backend.realtime.events.event import Event
from backend.realtime.events.event_type import EventType
from backend.realtime.services.realtime_service import RealtimeService


class RealtimePublishingAgentService:
    """Wraps a real AgentService, publishing Step*/Agent* events around ``execute_step``."""

    def __init__(self, inner: AgentService, realtime_service: RealtimeService) -> None:
        self._inner = inner
        self._realtime_service = realtime_service

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> Any:
        trace_id = current_trace_id.get()
        self._publish(EventType.STEP_STARTED, step, trace_id)
        self._publish(EventType.AGENT_STARTED, step, trace_id)
        try:
            result = await self._inner.execute_step(step, session_id)
        except Exception as exc:
            self._publish(EventType.STEP_FAILED, step, trace_id, error=str(exc))
            self._publish(EventType.AGENT_FAILED, step, trace_id, error=str(exc))
            raise
        self._publish(EventType.STEP_COMPLETED, step, trace_id)
        self._publish(EventType.AGENT_COMPLETED, step, trace_id)
        return result

    def _publish(self, event_type: EventType, step: ExecutionStep, trace_id: str | None, error: str | None = None) -> None:
        data: dict[str, Any] = {"step_name": step.name}
        if error is not None:
            data["error"] = error
        self._realtime_service.publish(
            Event(
                event_type=event_type,
                step_id=step.step_id,
                agent_name=step.node_name,
                trace_id=trace_id,
                data=data,
            )
        )
