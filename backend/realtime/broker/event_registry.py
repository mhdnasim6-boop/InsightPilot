"""EventRegistry: the discoverable catalog of every EventType this transport
layer supports — what ``GET /api/v1/realtime/events`` and the WebSocket
``subscribe`` action validate filter requests against.
"""

from backend.realtime.events.event_type import EventType
from backend.realtime.exceptions import UnknownEventTypeError

_CATEGORIES: dict[EventType, str] = {
    EventType.WORKFLOW_STARTED: "workflow",
    EventType.WORKFLOW_COMPLETED: "workflow",
    EventType.WORKFLOW_FAILED: "workflow",
    EventType.STEP_STARTED: "execution",
    EventType.STEP_COMPLETED: "execution",
    EventType.STEP_FAILED: "execution",
    EventType.APPROVAL_REQUESTED: "approval",
    EventType.APPROVAL_GRANTED: "approval",
    EventType.APPROVAL_REJECTED: "approval",
    EventType.AGENT_STARTED: "agent",
    EventType.AGENT_COMPLETED: "agent",
    EventType.AGENT_FAILED: "agent",
    EventType.TOOL_STARTED: "tool",
    EventType.TOOL_COMPLETED: "tool",
    EventType.TOOL_FAILED: "tool",
    EventType.AI_CALL_STARTED: "ai",
    EventType.AI_CALL_COMPLETED: "ai",
    EventType.MEMORY_STORED: "memory",
    EventType.REFLECTION_GENERATED: "reflection",
    EventType.OPTIMIZATION_GENERATED: "adaptive_planning",
    EventType.PLUGIN_LOADED: "plugin",
    EventType.PLUGIN_UNLOADED: "plugin",
    EventType.USER_LOGGED_IN: "security",
    EventType.USER_LOGGED_OUT: "security",
}


class EventRegistry:
    """Read-only catalog of every supported EventType and its category."""

    def list_event_types(self) -> list[EventType]:
        """Every EventType this transport layer can carry."""
        return list(EventType)

    def category_of(self, event_type: EventType) -> str:
        """Which subsystem category an EventType belongs to (for grouping in the UI)."""
        return _CATEGORIES[event_type]

    def validate(self, event_type: EventType) -> None:
        """Raise UnknownEventTypeError if ``event_type`` isn't a real EventType member.

        Exists for callers that receive a raw string (WebSocket messages,
        query params) and must confirm it against this registry before use.
        """
        if event_type not in EventType:
            raise UnknownEventTypeError(f"'{event_type}' is not a known event type.")
