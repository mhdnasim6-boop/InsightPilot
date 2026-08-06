"""ObservabilityPublisher: ToolStarted/Completed/Failed, PluginLoaded/Unloaded,
UserLoggedIn/UserLoggedOut.

The primary class here, ``RealtimePublishingTool``, wraps a real ``Tool``
exactly the way ``TracingTool`` does (same before/after/on-exception
shape, same delegation contract — tool tracing already lives in
``backend.observability``, so this event family is named for that
package, not for ``ObservabilityService`` itself, which is never
modified). Wired into each ``get_X_tool()`` provider
(``backend.dependencies.tools``), layered *around* the existing
``TracingTool`` wrap — both decorators delegate to the same inner tool,
so tracing and realtime publishing are fully independent add-ons.

This module also carries ``RealtimePublishingPluginRegistry`` and
``RealtimePublishingAuthenticationService`` — the remaining event
families (plugin lifecycle, login/logout) have no dedicated publisher
file of their own in this phase's folder structure, and both are, like
tool tracing, "observe the surrounding system, not a business workflow"
concerns, so they live here rather than being force-fit into
``execution_publisher``/``workflow_publisher``/``approval_publisher``/
``memory_publisher``/``ai_publisher``, none of which are a closer match.
"""

from typing import Any

from backend.observability.context import current_agent_name, current_trace_id
from backend.plugins.lifecycle.lifecycle import PluginRecord
from backend.plugins.registry.plugin_registry import PluginRegistry
from backend.realtime.events.event import Event
from backend.realtime.events.event_type import EventType
from backend.realtime.services.realtime_service import RealtimeService
from backend.security.authentication.authentication_service import AuthenticationService
from backend.security.models.login_response import LoginResponse
from backend.tools.base.tool import Tool


class RealtimePublishingTool(Tool[Any, Any]):
    """Wraps a real tool, publishing Tool* events for every call before delegating."""

    def __init__(self, inner: Tool[Any, Any], realtime_service: RealtimeService) -> None:
        self._inner = inner
        self._realtime_service = realtime_service
        self.name = inner.name
        self.description = inner.description
        self.input_model = inner.input_model
        self.output_model = inner.output_model

    async def execute(self, tool_input: Any) -> Any:
        self._publish(EventType.TOOL_STARTED)
        try:
            result = await self._inner.execute(tool_input)
        except Exception as exc:
            self._publish(EventType.TOOL_FAILED, error=str(exc))
            raise
        self._publish(EventType.TOOL_COMPLETED)
        return result

    def input_schema(self) -> dict[str, Any]:
        return self._inner.input_schema()

    def output_schema(self) -> dict[str, Any]:
        return self._inner.output_schema()

    def _publish(self, event_type: EventType, error: str | None = None) -> None:
        data: dict[str, Any] = {} if error is None else {"error": error}
        self._realtime_service.publish(
            Event(
                event_type=event_type,
                tool_name=self.name,
                agent_name=current_agent_name.get(),
                trace_id=current_trace_id.get(),
                data=data,
            )
        )


class RealtimePublishingPluginRegistry:
    """Wraps a real PluginRegistry, publishing Plugin* events around load/unload."""

    def __init__(self, inner: PluginRegistry, realtime_service: RealtimeService) -> None:
        self._inner = inner
        self._realtime_service = realtime_service

    def load(self, plugin_id: str | None = None) -> list[PluginRecord]:
        records = self._inner.load(plugin_id)
        for record in records:
            self._publish(EventType.PLUGIN_LOADED, record)
        return records

    def unload(self, plugin_id: str) -> PluginRecord:
        record = self._inner.unload(plugin_id)
        self._publish(EventType.PLUGIN_UNLOADED, record)
        return record

    def _publish(self, event_type: EventType, record: PluginRecord) -> None:
        self._realtime_service.publish(
            Event(
                event_type=event_type,
                data={
                    "plugin_id": record.manifest.id,
                    "version": record.manifest.metadata.version,
                    "state": record.state.value,
                },
            )
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class RealtimePublishingAuthenticationService:
    """Wraps a real AuthenticationService, publishing UserLoggedIn/UserLoggedOut around login/logout."""

    def __init__(self, inner: AuthenticationService, realtime_service: RealtimeService) -> None:
        self._inner = inner
        self._realtime_service = realtime_service

    def login(self, username: str, password: str) -> LoginResponse:
        response = self._inner.login(username, password)
        self._realtime_service.publish(
            Event(
                event_type=EventType.USER_LOGGED_IN,
                user_id=response.user.user_id,
                data={"username": response.user.username},
            )
        )
        return response

    def logout(self, refresh_token: str) -> None:
        self._inner.logout(refresh_token)
        self._realtime_service.publish(Event(event_type=EventType.USER_LOGGED_OUT))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
