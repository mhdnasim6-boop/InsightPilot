"""WebSocketManager: tracks live connections and broadcasts matching envelopes.

Registered as a listener on ``RealtimeEventBus`` (see
``RealtimeService.__init__``) — this is the *only* class in this whole
package that touches a real socket; everything upstream of it (events,
broker, replay, publishers) has no idea WebSockets exist, satisfying
this phase's own "no subsystem knows about WebSockets" rule one level
up as well.
"""

from backend.realtime.broker.subscription_manager import SubscriptionManager
from backend.realtime.events.event_envelope import EventEnvelope
from backend.realtime.websocket.websocket_connection import WebSocketConnection


class WebSocketManager:
    """Owns every live WebSocketConnection and fans out envelopes to matching ones."""

    def __init__(self, subscription_manager: SubscriptionManager) -> None:
        self._subscription_manager = subscription_manager
        self._connections: dict[str, WebSocketConnection] = {}

    async def connect(self, connection: WebSocketConnection) -> None:
        """Accept and register a new connection. Starts with no subscription filter."""
        await connection.accept()
        self._connections[connection.connection_id] = connection

    def disconnect(self, connection_id: str) -> None:
        """Deregister a connection and drop its subscription. A no-op if unknown."""
        self._connections.pop(connection_id, None)
        self._subscription_manager.unsubscribe(connection_id)

    def get(self, connection_id: str) -> WebSocketConnection | None:
        """The live connection for ``connection_id``, or ``None`` if not connected."""
        return self._connections.get(connection_id)

    def active_connection_ids(self) -> list[str]:
        """Every currently connected connection_id."""
        return list(self._connections.keys())

    def connection_count(self) -> int:
        """How many clients are currently connected."""
        return len(self._connections)

    async def broadcast(self, envelope: EventEnvelope) -> None:
        """Send ``envelope`` to every connection whose subscription filter matches it."""
        for connection_id, connection in list(self._connections.items()):
            if self._subscription_manager.matches(connection_id, envelope):
                await connection.send_envelope(envelope)

    async def send_to(self, connection_id: str, envelope: EventEnvelope) -> None:
        """Send one envelope directly to a specific connection, bypassing its filter (used for replay)."""
        connection = self._connections.get(connection_id)
        if connection is not None:
            await connection.send_envelope(envelope)
