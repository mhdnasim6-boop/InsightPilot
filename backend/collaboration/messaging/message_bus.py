"""MessageBus: the only channel agents/coordinator communicate through.

Agents never call each other directly in this architecture — every
delegation request, artifact-ready notice, and follow-up subtask request
is ``send()``/``broadcast()`` through here, persisted via
``CollaborationStore``, so ``history()`` is a complete, replayable audit
trail of one collaboration session.
"""

from backend.collaboration.models.collaboration_message import AgentMessage, MessageType
from backend.collaboration.stores.collaboration_store import CollaborationStore
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class MessageBus:
    """Send, receive, broadcast, and replay messages for one or more collaboration sessions."""

    def __init__(self, store: CollaborationStore) -> None:
        self._store = store

    def send(
        self,
        collaboration_id: str,
        from_agent: str,
        to_agent: str | None,
        message_type: MessageType,
        content: dict[str, object] | None = None,
    ) -> AgentMessage:
        """Send one message. ``to_agent=None`` is equivalent to ``broadcast()``."""
        message = AgentMessage(
            message_id=generate_id(),
            collaboration_id=collaboration_id,
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=content or {},
            created_at=utc_now(),
        )
        self._store.add_message(message)
        return message

    def broadcast(
        self,
        collaboration_id: str,
        from_agent: str,
        message_type: MessageType,
        content: dict[str, object] | None = None,
    ) -> AgentMessage:
        """Send one message to every agent in the session."""
        return self.send(collaboration_id, from_agent, None, message_type, content)

    def receive(self, collaboration_id: str, agent_name: str) -> list[AgentMessage]:
        """Every message addressed to ``agent_name`` or broadcast, in send order."""
        return [
            message
            for message in self._store.list_messages(collaboration_id)
            if message.to_agent in (None, agent_name)
        ]

    def history(self, collaboration_id: str) -> list[AgentMessage]:
        """Every message ever sent in this collaboration session, in send order."""
        return self._store.list_messages(collaboration_id)
