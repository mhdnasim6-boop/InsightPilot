"""RealtimeEventBus: in-process pub/sub for EventEnvelopes.

Structurally identical to ``backend.orchestration.events.bus.EventBus``/
``backend.planning.events.bus.PlanEventBus`` (sync or async listeners,
awaited via ``inspect.isawaitable``) — reused pattern, not a new one, per
this phase's own "reuse existing architecture" instruction.
``WebSocketManager.broadcast`` is registered as just another listener
here (see ``RealtimeService.__init__``), so the bus itself never imports
anything WebSocket-specific.
"""

import inspect
from collections.abc import Callable
from typing import Any

from backend.realtime.events.event_envelope import EventEnvelope

Listener = Callable[[EventEnvelope], Any]


class RealtimeEventBus:
    """Registers listeners and emits realtime EventEnvelopes to all of them."""

    def __init__(self) -> None:
        self._listeners: list[Listener] = []

    def subscribe(self, listener: Listener) -> None:
        """Register a listener to be called for every emitted envelope."""
        self._listeners.append(listener)

    def unsubscribe(self, listener: Listener) -> None:
        """Remove a previously registered listener. A no-op if not registered."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def emit(self, envelope: EventEnvelope) -> None:
        """Call every registered listener with the given envelope."""
        for listener in list(self._listeners):
            result = listener(envelope)
            if inspect.isawaitable(result):
                await result
