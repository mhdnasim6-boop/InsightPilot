"""Tests for backend.dependencies.realtime: singleton caching and that each
DI provider function constructs the right, correctly-wired object type.
"""

from backend.dependencies.realtime import (
    get_event_registry,
    get_realtime_event_bus,
    get_realtime_service,
    get_replay_buffer,
    get_replay_service,
    get_subscription_manager,
    get_websocket_manager,
    resolve_realtime_service,
)
from backend.realtime.broker.event_bus import RealtimeEventBus
from backend.realtime.broker.event_registry import EventRegistry
from backend.realtime.broker.subscription_manager import SubscriptionManager
from backend.realtime.replay.replay_buffer import ReplayBuffer
from backend.realtime.replay.replay_service import ReplayService
from backend.realtime.services.realtime_service import RealtimeService
from backend.realtime.websocket.websocket_manager import WebSocketManager


def test_singletons_are_cached_across_calls() -> None:
    assert get_realtime_event_bus() is get_realtime_event_bus()
    assert get_replay_buffer() is get_replay_buffer()
    assert get_subscription_manager() is get_subscription_manager()
    assert get_event_registry() is get_event_registry()


def test_get_replay_service_wraps_the_cached_buffer() -> None:
    replay_service = get_replay_service(replay_buffer=get_replay_buffer())
    assert isinstance(replay_service, ReplayService)


def test_get_websocket_manager_wraps_the_cached_subscription_manager() -> None:
    manager = get_websocket_manager(subscription_manager=get_subscription_manager())
    assert isinstance(manager, WebSocketManager)


def test_get_realtime_service_builds_correctly_wired_service() -> None:
    service = get_realtime_service(
        event_bus=get_realtime_event_bus(),
        replay_buffer=get_replay_buffer(),
        replay_service=get_replay_service(replay_buffer=get_replay_buffer()),
        subscription_manager=get_subscription_manager(),
        websocket_manager=get_websocket_manager(subscription_manager=get_subscription_manager()),
        event_registry=get_event_registry(),
    )

    assert isinstance(service, RealtimeService)
    assert len(service.list_event_types()) == 24


def test_get_realtime_service_is_cached() -> None:
    assert get_realtime_service(
        event_bus=get_realtime_event_bus(),
        replay_buffer=get_replay_buffer(),
        replay_service=get_replay_service(replay_buffer=get_replay_buffer()),
        subscription_manager=get_subscription_manager(),
        websocket_manager=get_websocket_manager(subscription_manager=get_subscription_manager()),
        event_registry=get_event_registry(),
    ) is get_realtime_service(
        event_bus=get_realtime_event_bus(),
        replay_buffer=get_replay_buffer(),
        replay_service=get_replay_service(replay_buffer=get_replay_buffer()),
        subscription_manager=get_subscription_manager(),
        websocket_manager=get_websocket_manager(subscription_manager=get_subscription_manager()),
        event_registry=get_event_registry(),
    )


def test_resolve_realtime_service_matches_the_cached_di_singleton() -> None:
    """``resolve_realtime_service()`` (used outside a request, e.g. by
    ``backend.main``'s own startup/AuthenticationMiddleware wiring) must
    resolve to the exact same singleton a real request's own
    ``Depends(get_realtime_service)`` would — same reasoning
    ``test_workflows_dependencies.py`` documents for its own bare-call cases."""
    assert resolve_realtime_service() is get_realtime_service(
        event_bus=get_realtime_event_bus(),
        replay_buffer=get_replay_buffer(),
        replay_service=get_replay_service(replay_buffer=get_replay_buffer()),
        subscription_manager=get_subscription_manager(),
        websocket_manager=get_websocket_manager(subscription_manager=get_subscription_manager()),
        event_registry=get_event_registry(),
    )


def test_event_bus_is_a_realtime_event_bus() -> None:
    assert isinstance(get_realtime_event_bus(), RealtimeEventBus)


def test_replay_buffer_is_a_replay_buffer() -> None:
    assert isinstance(get_replay_buffer(), ReplayBuffer)


def test_subscription_manager_is_a_subscription_manager() -> None:
    assert isinstance(get_subscription_manager(), SubscriptionManager)


def test_event_registry_is_an_event_registry() -> None:
    assert isinstance(get_event_registry(), EventRegistry)
