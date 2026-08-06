"""Realtime endpoints: discover event types, inspect active subscriptions,
and replay recent history — thin wrappers over ``RealtimeService``, the
one and only public entry point this layer exposes (the live stream
itself is the WebSocket endpoint, ``/ws/events``, registered directly on
the app in ``backend.main`` rather than under this versioned REST prefix).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from backend.dependencies.realtime import get_realtime_service
from backend.realtime.broker.subscription_manager import SubscriptionFilter
from backend.realtime.events.event_envelope import EventEnvelope
from backend.realtime.events.event_type import EventType
from backend.realtime.exceptions import InvalidReplayRequestError
from backend.realtime.services.realtime_service import RealtimeService
from backend.schemas.response import SuccessResponse
from backend.security.authorization.permission import Permission
from backend.security.middleware.authorization import require_permission
from backend.security.models.authenticated_user import AuthenticatedUser

router = APIRouter(prefix="/realtime")


@router.get("/events", response_model=SuccessResponse[list[EventType]], summary="List supported event types")
async def list_event_types(
    realtime_service: RealtimeService = Depends(get_realtime_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[list[EventType]]:
    """Every EventType this transport layer can carry — what a WebSocket ``subscribe``
    or this endpoint's own ``/replay`` may filter by."""
    return SuccessResponse.ok(data=realtime_service.list_event_types(), message="Event types fetched.")


@router.get("/subscriptions", response_model=SuccessResponse[list[str]], summary="List active subscriptions")
async def list_subscriptions(
    realtime_service: RealtimeService = Depends(get_realtime_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[list[str]]:
    """Every connection_id with an active WebSocket subscription filter right now."""
    return SuccessResponse.ok(data=realtime_service.list_subscriptions(), message="Active subscriptions fetched.")


@router.get("/replay", response_model=SuccessResponse[list[EventEnvelope]], summary="Replay recent event history")
async def replay_events(
    count: int | None = Query(default=None, description="Return the last N events."),
    since: datetime | None = Query(default=None, description="Return every event published after this timestamp."),
    event_type: list[EventType] | None = Query(default=None, description="Restrict to these event types."),
    workflow_id: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    agent_name: str | None = Query(default=None),
    realtime_service: RealtimeService = Depends(get_realtime_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[list[EventEnvelope]]:
    """Replay recorded events — exactly one of ``count``/``since``, optionally narrowed
    by event type / workflow / trace / user / agent. Neither means "the whole buffer."""
    if count is not None and since is not None:
        raise InvalidReplayRequestError("Pass either 'count' or 'since', not both.")
    subscription_filter = SubscriptionFilter(
        event_types=frozenset(event_type or []),
        workflow_id=workflow_id, trace_id=trace_id, user_id=user_id, agent_name=agent_name,
    )
    envelopes = realtime_service.replay(count=count, since=since, subscription_filter=subscription_filter)
    return SuccessResponse.ok(data=envelopes, message=f"{len(envelopes)} event(s) replayed.")
