"""Simple pub/sub event bus for orchestration events.

Listeners may be sync or async callables — the bus awaits whichever it
gets. No filtering by event type at the bus level; a listener that only
cares about certain events should check ``isinstance(event, ...)`` itself.
"""

import inspect
from collections.abc import Callable
from typing import Any

from backend.orchestration.events.events import OrchestrationEvent

Listener = Callable[[OrchestrationEvent], Any]


class EventBus:
    """Registers listeners and emits orchestration events to all of them."""

    def __init__(self) -> None:
        self._listeners: list[Listener] = []

    def subscribe(self, listener: Listener) -> None:
        """Register a listener to be called for every emitted event."""
        self._listeners.append(listener)

    async def emit(self, event: OrchestrationEvent) -> None:
        """Call every registered listener with the given event."""
        for listener in self._listeners:
            result = listener(event)
            if inspect.isawaitable(result):
                await result
