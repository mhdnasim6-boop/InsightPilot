"""RealtimeService: the ONLY public API of the realtime layer.

Per this phase's own architecture rule: every publisher (``publishers/*``)
calls only ``RealtimeService.publish()``; nothing upstream of this class
knows a WebSocket, a replay buffer, or a subscription filter exists.
This class composes the broker (``RealtimeEventBus``), the replay layer
(``ReplayBuffer``/``ReplayService``), and the WebSocket layer
(``SubscriptionManager``/``WebSocketManager``) — wiring ``WebSocketManager.broadcast``
in as just another event-bus listener, so broadcasting is "forward to
whichever listeners are subscribed," not a special case.

``publish()`` is deliberately synchronous and safe to call from both
sync and async decorator methods (most of the 8 wrapped subsystems mix
sync and async public methods) — it always records the event into the
replay buffer synchronously, then *best-effort* schedules the async
WebSocket fan-out via ``asyncio.get_running_loop().create_task(...)``.
Outside a running event loop (a plain synchronous unit test constructing
a publisher directly, for instance) there is nothing to schedule onto,
so the event is still durably recorded (and later replayable) even
though no live broadcast happens — this mirrors the existing
"observability_service call is best-effort, never blocks/breaks the
caller" convention already used by ``TracingTool``/``AIService``.
"""

import asyncio
from datetime import datetime

from backend.realtime.broker.event_bus import RealtimeEventBus
from backend.realtime.broker.event_registry import EventRegistry
from backend.realtime.broker.subscription_manager import (
    SubscriptionFilter,
    SubscriptionManager,
)
from backend.realtime.events.event import Event
from backend.realtime.events.event_envelope import EventEnvelope
from backend.realtime.events.event_type import EventType
from backend.realtime.replay.replay_buffer import ReplayBuffer
from backend.realtime.replay.replay_service import ReplayService
from backend.realtime.websocket.websocket_connection import WebSocketConnection
from backend.realtime.websocket.websocket_manager import WebSocketManager


class RealtimeService:
    """Publish typed events; subscribe, filter, and replay them. The only public surface."""

    def __init__(
        self,
        event_bus: RealtimeEventBus,
        replay_buffer: ReplayBuffer,
        replay_service: ReplayService,
        subscription_manager: SubscriptionManager,
        websocket_manager: WebSocketManager,
        event_registry: EventRegistry,
    ) -> None:
        self._event_bus = event_bus
        self._replay_buffer = replay_buffer
        self._replay_service = replay_service
        self._subscription_manager = subscription_manager
        self._websocket_manager = websocket_manager
        self._event_registry = event_registry
        self._event_bus.subscribe(self._websocket_manager.broadcast)

    # -- Publishing ---------------------------------------------------------

    def publish(self, event: Event) -> EventEnvelope:
        """Record ``event`` and best-effort broadcast it to subscribed WebSocket clients.

        Safe to call from sync or async code — see this module's own docstring.
        """
        envelope = self._replay_buffer.make_event_envelope(event)
        self._replay_buffer.append(envelope)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return envelope
        loop.create_task(self._event_bus.emit(envelope))
        return envelope

    async def publish_async(self, event: Event) -> EventEnvelope:
        """Record ``event`` and broadcast it, awaiting delivery to every subscriber."""
        envelope = self._replay_buffer.make_event_envelope(event)
        self._replay_buffer.append(envelope)
        await self._event_bus.emit(envelope)
        return envelope

    # -- Discovery ------------------------------------------------------------

    def list_event_types(self) -> list[EventType]:
        """Every EventType this transport layer supports."""
        return self._event_registry.list_event_types()

    def list_subscriptions(self) -> list[str]:
        """Every connection_id with an active subscription filter."""
        return self._subscription_manager.active_connection_ids()

    # -- Replay -----------------------------------------------------------------

    def replay(
        self,
        count: int | None = None,
        since: datetime | None = None,
        subscription_filter: SubscriptionFilter | None = None,
    ) -> list[EventEnvelope]:
        """Query recorded history — see ``ReplayService.replay`` for semantics."""
        return self._replay_service.replay(count=count, since=since, subscription_filter=subscription_filter)

    # -- WebSocket lifecycle ------------------------------------------------

    async def connect(self, connection: WebSocketConnection) -> None:
        """Accept and register a new WebSocket connection."""
        await self._websocket_manager.connect(connection)

    def disconnect(self, connection_id: str) -> None:
        """Deregister a WebSocket connection and drop its subscription."""
        self._websocket_manager.disconnect(connection_id)

    def subscribe(self, connection_id: str, subscription_filter: SubscriptionFilter | None = None) -> None:
        """Set (or replace) a connection's subscription filter."""
        self._subscription_manager.subscribe(connection_id, subscription_filter)

    def unsubscribe(self, connection_id: str) -> None:
        """Clear a connection's subscription filter."""
        self._subscription_manager.unsubscribe(connection_id)

    async def replay_to(
        self,
        connection_id: str,
        count: int | None = None,
        since: datetime | None = None,
    ) -> list[EventEnvelope]:
        """Replay matching history directly to one connection (the WebSocket ``replay`` action)."""
        subscription_filter = self._subscription_manager.filter_for(connection_id)
        envelopes = self.replay(count=count, since=since, subscription_filter=subscription_filter)
        for envelope in envelopes:
            await self._websocket_manager.send_to(connection_id, envelope)
        return envelopes
