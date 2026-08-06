"""ExecutionCoordinator: assembles dynamic agent discovery + dependency-
graph validation + plan construction into one preparation step —
"figure out what to run and confirm it's runnable," before
``WorkflowEngine`` actually runs it.

No execution happens here. Every real decision is delegated: agent
existence to ``WorkflowDispatcher`` (itself wrapping the existing
``AgentCapabilityRegistry``), ordering/cycles to
``WorkflowDependencyGraph`` (itself wrapping ``topological_order()``),
and plan construction to ``WorkflowBuilder``.
"""

from backend.planning.models.plan import ExecutionPlan
from backend.workflows.coordination.dependency_graph import WorkflowDependencyGraph
from backend.workflows.exceptions import UnknownAgentError
from backend.workflows.execution.workflow_dispatcher import WorkflowDispatcher
from backend.workflows.models.workflow_step import WorkflowStep
from backend.workflows.planner.workflow_builder import build_execution_plan


class ExecutionCoordinator:
    """Validates dynamic agent references and step ordering, then builds a real ExecutionPlan."""

    def __init__(self, dispatcher: WorkflowDispatcher, dependency_graph: WorkflowDependencyGraph) -> None:
        self._dispatcher = dispatcher
        self._dependency_graph = dependency_graph

    def prepare(self, plan_id: str, goal: str | None, steps: list[WorkflowStep], session_id: str | None) -> ExecutionPlan:
        """Validate agent references and ordering, then build a DRAFT ExecutionPlan.
        Raises UnknownAgentError for a step naming an agent that isn't currently
        discoverable, or WorkflowCycleError (via WorkflowDependencyGraph) for a cycle."""
        known_agents = self._dispatcher.discover_agent_names()
        for step in steps:
            if step.kind == "agent" and step.node_name not in known_agents:
                raise UnknownAgentError(
                    f"Step '{step.step_id}' references unknown agent '{step.node_name}'. "
                    f"Currently discoverable agents: {sorted(known_agents)}."
                )

        self._dependency_graph.order(steps)  # raises WorkflowCycleError if steps contain a cycle
        return build_execution_plan(plan_id=plan_id, goal=goal, steps=steps, session_id=session_id)
