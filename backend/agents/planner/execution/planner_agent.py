"""PlannerAgent: orchestrates the existing PlannerService for one ExecutionStep.

One ``PlannerService.plan()`` call — never the prompt templates, parser,
or validator directly, and no planning logic of its own. This is where
dynamic agent discovery actually happens: when an ``AgentCapabilityRegistry``
is supplied, ``available_services``/``available_service_descriptions``
are sourced from its ``discover()`` — the exact same registry
``CollaborationService.discover_capabilities()`` itself wraps (see
``backend.collaboration.coordinator.capability_registry``) — instead of
reading ``GraphBuilder`` directly. Planner depends on the registry
itself rather than the full ``CollaborationService`` deliberately: that
service's own collaboration-scoped execution engine transitively depends
on this same module's ``get_planner_agent_service()`` provider (it
dispatches to every *other* agent service the same way), so depending on
the full service here would be a genuine dependency cycle. The registry
has no such problem — it only ever needs ``GraphBuilder``. Without one
(the graph-embedded ``PlannerAgentNode`` path), discovery falls back to
reading ``GraphBuilder`` directly, exactly as before this phase — zero
behavior change for that path. ``PlannerService`` itself never queries
either one directly — by design, per its own ``PlannerInput`` docstring
— so this class is where that caller-side responsibility lives.

A downstream failure (malformed AI response, plan validation failure)
degrades to a FAILED ``PlannerAgentResult`` rather than a crash — only
malformed *input* (missing ``user_request``) raises immediately, the
same split every other agent's own execution class makes.
"""

import time
from typing import TYPE_CHECKING

from loguru import logger

from backend.agents.planner.exceptions import (
    InvalidPlannerAgentInputError,
    PlannerError,
)
from backend.agents.planner.models.io import PlannerInput
from backend.agents.planner.models.result import PlannerAgentResult
from backend.ingestion.models.dataset import BusinessDataset
from backend.orchestration.graph.builder import GraphBuilder
from backend.orchestration.nodes.approval_node import APPROVAL_NODE_PREFIX
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.step import ExecutionStep
from backend.services.planner_service import PlannerService

if TYPE_CHECKING:
    from backend.collaboration.coordinator.capability_registry import (
        AgentCapabilityRegistry,
    )

_NON_AGENT_NODE_NAMES = {"planner", "router", "end"}


class PlannerAgent:
    """Runs PlannerService.plan() for one step, with dynamically discovered agents."""

    def __init__(
        self,
        planner_service: PlannerService,
        graph_builder: GraphBuilder,
        capability_registry: "AgentCapabilityRegistry | None" = None,
    ) -> None:
        self._planner_service = planner_service
        self._graph_builder = graph_builder
        self._capability_registry = capability_registry

    async def execute(self, step: ExecutionStep, session_id: str | None) -> PlannerAgentResult:
        """Produce a plan for ``step`` and return the outcome.

        Raises ``InvalidPlannerAgentInputError`` if ``step.inputs`` has no
        ``user_request``. A planning failure (malformed AI response, or a
        generated plan that fails validation even against the freshly
        discovered agents) is captured in the returned result's
        ``status``/``warnings`` instead of raising.
        """
        planner_input = self._build_planner_input(step, session_id)

        start = time.perf_counter()
        warnings: list[str] = []
        planner_output = None
        status = ExecutionStatus.COMPLETED

        try:
            planner_output = await self._planner_service.plan(planner_input)
        except PlannerError as exc:
            logger.exception("PlannerAgent step '{}' failed", step.step_id)
            warnings.append(str(exc))
            status = ExecutionStatus.FAILED

        execution_time = time.perf_counter() - start
        return PlannerAgentResult(
            step_id=step.step_id,
            status=status,
            planner_output=planner_output,
            warnings=warnings,
            execution_time=execution_time,
            metadata={
                "session_id": session_id,
                "available_services": planner_input.available_services,
            },
        )

    def _build_planner_input(self, step: ExecutionStep, session_id: str | None) -> PlannerInput:
        user_request = step.inputs.get("user_request")
        if not user_request or not str(user_request).strip():
            raise InvalidPlannerAgentInputError(
                f"PlannerAgent step '{step.step_id}' requires a non-empty 'user_request' in step.inputs."
            )

        available_services, available_service_descriptions = self._discover_agents()

        return PlannerInput(
            user_request=str(user_request),
            session_id=session_id,
            conversation_summary=step.inputs.get("conversation_summary"),
            uploaded_datasets=[
                BusinessDataset.model_validate(dataset) for dataset in step.inputs.get("uploaded_datasets", [])
            ],
            available_services=available_services,
            available_service_descriptions=available_service_descriptions,
            available_sql_connections=list(step.inputs.get("available_sql_connections", [])),
            available_browser_context=list(step.inputs.get("available_browser_context", [])),
            existing_reports=list(step.inputs.get("existing_reports", [])),
            user_preferences=dict(step.inputs.get("user_preferences", {})),
            metadata={"step_id": step.step_id},
        )

    def _discover_agents(self) -> tuple[list[str], dict[str, str]]:
        """Discover every currently available agent — via AgentCapabilityRegistry if wired, else GraphBuilder.

        Called fresh on every request — this is what makes agent
        discovery genuinely dynamic rather than a hardcoded list: if an
        agent is ever added or removed, this reflects it with no code
        change here.
        """
        if self._capability_registry is not None:
            capabilities = self._capability_registry.discover()
            available_services = [capability.name for capability in capabilities]
            available_service_descriptions = {
                capability.name: capability.description for capability in capabilities if capability.description
            }
            return available_services, available_service_descriptions

        graph_metadata = self._graph_builder.export()
        agent_nodes = [
            node
            for node in graph_metadata.nodes
            if node.name not in _NON_AGENT_NODE_NAMES and not node.name.startswith(APPROVAL_NODE_PREFIX)
        ]
        available_services = [node.name for node in agent_nodes]
        available_service_descriptions = {
            node.name: str(node.details["description"]) for node in agent_nodes if node.details.get("description")
        }
        return available_services, available_service_descriptions
