"""Realtime layer providers: broker, replay, WebSocket manager, and the
top-level RealtimeService — every collaborator cached, mirroring
``backend.dependencies.memory``'s own convention (every one of
``RealtimeService``'s own dependencies here is itself an already-cached
singleton, so ``@lru_cache`` genuinely hits and every request/WebSocket
connection shares the same event bus/replay buffer/subscription state).
"""

from functools import lru_cache

from fastapi import Depends

from backend.realtime.broker.event_bus import RealtimeEventBus
from backend.realtime.broker.event_registry import EventRegistry
from backend.realtime.broker.subscription_manager import SubscriptionManager
from backend.realtime.replay.replay_buffer import ReplayBuffer
from backend.realtime.replay.replay_service import ReplayService
from backend.realtime.services.realtime_service import RealtimeService
from backend.realtime.websocket.websocket_manager import WebSocketManager


@lru_cache
def get_realtime_event_bus() -> RealtimeEventBus:
    """Return the process-wide RealtimeEventBus singleton."""
    return RealtimeEventBus()


@lru_cache
def get_replay_buffer() -> ReplayBuffer:
    """Return the process-wide ReplayBuffer singleton — every published event lives here."""
    return ReplayBuffer()


@lru_cache
def get_replay_service(replay_buffer: ReplayBuffer = Depends(get_replay_buffer)) -> ReplayService:
    """Return the process-wide ReplayService singleton."""
    return ReplayService(replay_buffer)


@lru_cache
def get_subscription_manager() -> SubscriptionManager:
    """Return the process-wide SubscriptionManager singleton — every connection's filter lives here."""
    return SubscriptionManager()


@lru_cache
def get_event_registry() -> EventRegistry:
    """Return the process-wide EventRegistry singleton. Stateless — cached for identity reuse."""
    return EventRegistry()


@lru_cache
def get_websocket_manager(
    subscription_manager: SubscriptionManager = Depends(get_subscription_manager),
) -> WebSocketManager:
    """Return the process-wide WebSocketManager singleton — every live connection lives here."""
    return WebSocketManager(subscription_manager)


@lru_cache
def get_realtime_service(
    event_bus: RealtimeEventBus = Depends(get_realtime_event_bus),
    replay_buffer: ReplayBuffer = Depends(get_replay_buffer),
    replay_service: ReplayService = Depends(get_replay_service),
    subscription_manager: SubscriptionManager = Depends(get_subscription_manager),
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
    event_registry: EventRegistry = Depends(get_event_registry),
) -> RealtimeService:
    """Provide the RealtimeService — the only object anything should use to publish or observe realtime events."""
    return RealtimeService(
        event_bus, replay_buffer, replay_service, subscription_manager, websocket_manager, event_registry
    )


def resolve_realtime_service() -> RealtimeService:
    """Build the process-wide RealtimeService outside a FastAPI request.

    Called from ``backend.dependencies.security.resolve_authentication_service()``
    so the singleton ``AuthenticationService`` built for ``AuthenticationMiddleware``
    at app startup is wrapped with the same realtime publishing every
    request-scoped ``Depends(get_authentication_service)`` gets — mirrors
    ``backend.dependencies.operations``' own ``resolve_startup_manager()`` pattern.
    """
    return get_realtime_service(
        event_bus=get_realtime_event_bus(),
        replay_buffer=get_replay_buffer(),
        replay_service=get_replay_service(replay_buffer=get_replay_buffer()),
        subscription_manager=get_subscription_manager(),
        websocket_manager=get_websocket_manager(subscription_manager=get_subscription_manager()),
        event_registry=get_event_registry(),
    )
