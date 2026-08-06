"""NodeDispatcher: routes one ExecutionStep to its registered agent service, by node_name.

A ``dict[str, AgentService]`` registry, populated via DI — mirrors
``ToolRegistry``'s own "dynamic, name-keyed, no hardcoded list" design
(``backend.tools.registry.tool_registry``). Every existing agent service
(``FileAgentService``, ``SQLAgentService``, ``BrowserAgentService``,
``ReportAgentService``, ``ExecutiveSummaryService``, ``PlannerAgentService``)
already shares the exact same ``execute_step(step, session_id) -> Result``
signature — confirmed structurally, not via a shared base class — so
``AgentService`` below is a ``Protocol``, and registering a future agent
needs only one ``register()`` call at DI wiring time, never a new
if/elif branch here.
"""

from typing import Any, Protocol, runtime_checkable

from backend.execution.exceptions.errors import UnknownNodeError
from backend.planning.models.step import ExecutionStep


@runtime_checkable
class AgentService(Protocol):
    """Structural contract every dispatchable agent service already satisfies."""

    async def execute_step(self, step: ExecutionStep, session_id: str | None) -> Any: ...


class NodeDispatcher:
    """Dispatches one ExecutionStep to whichever agent service is registered for its node_name."""

    def __init__(self) -> None:
        self._services: dict[str, AgentService] = {}

    def register(self, node_name: str, service: AgentService) -> None:
        """Register (or overwrite) the agent service that handles ``node_name``."""
        self._services[node_name] = service

    def is_registered(self, node_name: str) -> bool:
        """Whether a service is registered for ``node_name``."""
        return node_name in self._services

    def registered_node_names(self) -> list[str]:
        """Every node_name with a registered agent service."""
        return sorted(self._services.keys())

    async def dispatch(self, step: ExecutionStep, session_id: str | None) -> Any:
        """Run ``step`` via its registered agent service.

        Raises UnknownNodeError if ``step.node_name`` has no registered
        service — everything else (a bad AI call, malformed input) is
        the agent service's own concern, exactly as it is today.
        """
        service = self._services.get(step.node_name)
        if service is None:
            raise UnknownNodeError(f"No agent service registered for node_name '{step.node_name}'.")
        return await service.execute_step(step, session_id)
