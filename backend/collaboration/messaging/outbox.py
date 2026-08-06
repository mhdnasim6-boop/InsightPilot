"""Outbox: one agent's own write-only view onto the MessageBus.

The mirror image of ``Inbox`` — scopes ``send()``/``broadcast()`` to one
agent's own name as ``from_agent`` so a caller acting "as" an agent never
has to repeat it.
"""

from backend.collaboration.messaging.message_bus import MessageBus
from backend.collaboration.models.collaboration_message import AgentMessage, MessageType


class Outbox:
    """One agent's own channel for sending/broadcasting messages as itself."""

    def __init__(self, bus: MessageBus, agent_name: str) -> None:
        self._bus = bus
        self._agent_name = agent_name

    def send(
        self, collaboration_id: str, to_agent: str, message_type: MessageType, content: dict[str, object] | None = None
    ) -> AgentMessage:
        return self._bus.send(collaboration_id, self._agent_name, to_agent, message_type, content)

    def broadcast(
        self, collaboration_id: str, message_type: MessageType, content: dict[str, object] | None = None
    ) -> AgentMessage:
        return self._bus.broadcast(collaboration_id, self._agent_name, message_type, content)
