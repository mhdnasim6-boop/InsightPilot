"""Pub/sub event bus for planning events.

Structurally identical to ``backend.orchestration.events.bus.EventBus``
(sync or async listeners, awaited via ``inspect.isawaitable``) — kept as
a separate class rather than shared because planning and orchestration
events are distinct type families with no common base.
"""

import inspect
from collections.abc import Callable
from typing import Any

from backend.planning.events.events import PlanningEvent

PlanListener = Callable[[PlanningEvent], Any]


class PlanEventBus:
    """Registers listeners and emits planning events to all of them."""

    def __init__(self) -> None:
        self._listeners: list[PlanListener] = []

    def subscribe(self, listener: PlanListener) -> None:
        """Register a listener to be called for every emitted event."""
        self._listeners.append(listener)

    async def emit(self, event: PlanningEvent) -> None:
        """Call every registered listener with the given event."""
        for listener in self._listeners:
            result = listener(event)
            if inspect.isawaitable(result):
                await result
