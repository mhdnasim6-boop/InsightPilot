"""Inbox: one agent's own read-only view onto the MessageBus.

A thin convenience, not a parallel channel — every message still lives
in ``CollaborationStore`` via ``MessageBus``; this just scopes
``receive()`` to one agent's own name so a caller acting "as" an agent
never has to repeat it.
"""

from backend.collaboration.messaging.message_bus import MessageBus
from backend.collaboration.models.collaboration_message import AgentMessage


class Inbox:
    """One agent's own view of messages addressed to it (directly or by broadcast)."""

    def __init__(self, bus: MessageBus, agent_name: str) -> None:
        self._bus = bus
        self._agent_name = agent_name

    def messages(self, collaboration_id: str) -> list[AgentMessage]:
        return self._bus.receive(collaboration_id, self._agent_name)
