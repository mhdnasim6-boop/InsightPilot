"""WebSocketConnection: one live client connection, identified and sendable to.

Thin wrapper around FastAPI's own ``WebSocket`` — gives every connection
a stable ``connection_id`` (independent of the underlying socket object)
so ``SubscriptionManager``/``WebSocketManager`` can key on a plain string,
and centralizes envelope serialization through ``EventSerializer``.
"""

from fastapi import WebSocket

from backend.realtime.events.event_envelope import EventEnvelope
from backend.realtime.events.event_serializer import EventSerializer
from backend.utils.ids import generate_id


class WebSocketConnection:
    """One connected WebSocket client."""

    def __init__(self, websocket: WebSocket, connection_id: str | None = None, user_id: str | None = None) -> None:
        self.connection_id = connection_id or generate_id()
        self.user_id = user_id
        self._websocket = websocket

    async def accept(self) -> None:
        """Accept the underlying WebSocket handshake."""
        await self._websocket.accept()

    async def send_envelope(self, envelope: EventEnvelope) -> None:
        """Send one EventEnvelope to this client as JSON."""
        await self._websocket.send_json(EventSerializer.to_dict(envelope))

    async def send_json(self, message: dict) -> None:
        """Send an arbitrary JSON message (acks, heartbeats, errors) to this client."""
        await self._websocket.send_json(message)

    async def receive_json(self) -> dict:
        """Receive one JSON message from this client."""
        return await self._websocket.receive_json()

    async def close(self, code: int = 1000) -> None:
        """Close the underlying WebSocket connection."""
        await self._websocket.close(code=code)
