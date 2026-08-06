"""WebSocket router: ``/ws/events`` — subscribe/unsubscribe/heartbeat/replay.

Authentication here is deliberately manual (a ``token`` query parameter,
verified via the real ``AuthenticationService.authenticate()``) rather
than reused from ``AuthenticationMiddleware``: that middleware is a
Starlette ``BaseHTTPMiddleware``, which never runs for WebSocket
handshakes (Starlette only invokes ``BaseHTTPMiddleware`` for the HTTP
protocol) — confirmed from that middleware's own class, not assumed.
This still reuses the *same* ``AuthenticationService.authenticate()``
call the middleware itself uses, so no new verification logic exists,
only a new place to call the existing one from.

Message protocol (client -> server, one JSON object per message):
    {"action": "subscribe", "event_types": [...], "workflow_id": ..., "trace_id": ..., "user_id": ..., "agent_name": ...}
    {"action": "unsubscribe"}
    {"action": "heartbeat"}
    {"action": "replay", "count": 10, "since": "2026-01-01T00:00:00Z"}
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from backend.dependencies.realtime import get_realtime_service
from backend.dependencies.security import get_authentication_service
from backend.realtime.broker.subscription_manager import SubscriptionFilter
from backend.realtime.events.event_type import EventType
from backend.realtime.services.realtime_service import RealtimeService
from backend.realtime.websocket.websocket_connection import WebSocketConnection
from backend.security.authentication.authentication_service import AuthenticationService
from backend.security.exceptions import SecurityError
from backend.utils.time import utc_now

router = APIRouter()


@router.websocket("/ws/events")
async def events_websocket(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    realtime_service: RealtimeService = Depends(get_realtime_service),
    authentication_service: AuthenticationService = Depends(get_authentication_service),
) -> None:
    """Live event stream. Requires a valid access token as ``?token=``."""
    user_id: str | None = None
    if token is not None:
        try:
            user_id = authentication_service.authenticate(token).user_id
        except SecurityError:
            await websocket.close(code=4401)
            return
    else:
        await websocket.close(code=4401)
        return

    connection = WebSocketConnection(websocket, user_id=user_id)
    await realtime_service.connect(connection)
    realtime_service.subscribe(connection.connection_id)  # default: no filter, everything

    try:
        while True:
            message = await connection.receive_json()
            await _handle_message(connection, realtime_service, message)
    except WebSocketDisconnect:
        realtime_service.disconnect(connection.connection_id)


async def _handle_message(connection: WebSocketConnection, realtime_service: RealtimeService, message: dict) -> None:
    action = message.get("action")
    if action == "subscribe":
        realtime_service.subscribe(connection.connection_id, _build_filter(message))
        await connection.send_json({"type": "subscribed", "connection_id": connection.connection_id})
    elif action == "unsubscribe":
        realtime_service.unsubscribe(connection.connection_id)
        await connection.send_json({"type": "unsubscribed", "connection_id": connection.connection_id})
    elif action == "heartbeat":
        await connection.send_json({"type": "heartbeat_ack", "timestamp": utc_now().isoformat()})
    elif action == "replay":
        since = _parse_since(message.get("since"))
        await realtime_service.replay_to(connection.connection_id, count=message.get("count"), since=since)
    else:
        await connection.send_json({"type": "error", "message": f"Unknown action '{action}'."})


def _build_filter(message: dict) -> SubscriptionFilter:
    raw_types = message.get("event_types") or []
    return SubscriptionFilter(
        event_types=frozenset(EventType(value) for value in raw_types),
        workflow_id=message.get("workflow_id"),
        trace_id=message.get("trace_id"),
        user_id=message.get("user_id"),
        agent_name=message.get("agent_name"),
    )


def _parse_since(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw) if raw else None
