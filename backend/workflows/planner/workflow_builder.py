"""WorkflowBuilder: constructs a Workflow either from explicit steps (the
REST-authored path) or from a natural-language objective by delegating
to the real PlannerAgent/PlannerService (Phase 8/21) — never a second
planning implementation.

``build_execution_plan()`` is the one place a WorkflowStep list becomes
a real ``ExecutionPlan`` — a pure, structural conversion reused by
``ExecutionCoordinator`` and by ``WorkflowService`` itself; no validation,
optimization, or execution decision is made here.
"""

from backend.agents.planner.models.io import PlannerInput, PlannerOutput
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.services.planner_service import PlannerService
from backend.utils.ids import generate_id
from backend.utils.time import utc_now
from backend.workflows.coordination.dependency_graph import to_execution_steps
from backend.workflows.execution.workflow_dispatcher import WorkflowDispatcher
from backend.workflows.models.workflow import Workflow
from backend.workflows.models.workflow_definition import WorkflowDefinition
from backend.workflows.models.workflow_status import WorkflowStatus
from backend.workflows.models.workflow_step import WorkflowStep


def build_execution_plan(
    plan_id: str, goal: str | None, steps: list[WorkflowStep], session_id: str | None,
) -> ExecutionPlan:
    """Convert a WorkflowStep list into a real, DRAFT ExecutionPlan — a pure structural
    mapping, no validation/optimization/execution logic of its own."""
    now = utc_now()
    return ExecutionPlan(
        plan_id=plan_id, session_id=session_id, goal=goal, status=PlanStatus.DRAFT,
        steps=to_execution_steps(steps), created_at=now, updated_at=now,
    )


class WorkflowBuilder:
    """Builds Workflows from explicit steps, or from an objective via the real PlannerAgent."""

    def __init__(self, dispatcher: WorkflowDispatcher, planner_service: PlannerService | None = None) -> None:
        self._dispatcher = dispatcher
        self._planner_service = planner_service

    def build_from_steps(
        self, name: str, description: str, steps: list[WorkflowStep], tags: list[str] | None = None,
    ) -> Workflow:
        """Construct a new, DRAFT Workflow from explicitly authored steps."""
        now = utc_now()
        definition = WorkflowDefinition(name=name, description=description, steps=steps, tags=tags or [])
        return Workflow(
            workflow_id=generate_id(), definition=definition, status=WorkflowStatus.DRAFT, created_at=now, updated_at=now,
        )

    async def build_from_objective(
        self, objective: str, session_id: str | None = None, tags: list[str] | None = None,
    ) -> Workflow:
        """Construct a new, DRAFT Workflow by asking the real PlannerAgent to plan ``objective``.

        Populates ``PlannerInput.available_services``/``available_service_descriptions``
        from the same dynamic ``WorkflowDispatcher`` discovery every other part of this
        package uses — the Planner never hardcodes which agents exist either.
        Raises RuntimeError if no PlannerService was wired.
        """
        if self._planner_service is None:
            raise RuntimeError("No PlannerService is configured for this WorkflowBuilder.")

        capabilities = self._dispatcher.discover_agents()
        planner_input = PlannerInput(
            user_request=objective,
            session_id=session_id,
            available_services=[capability.name for capability in capabilities],
            available_service_descriptions={capability.name: capability.description for capability in capabilities},
        )
        output: PlannerOutput = await self._planner_service.plan(planner_input)

        steps = [
            WorkflowStep(
                step_id=step.step_id, name=step.name, description=step.description, node_name=step.node_name,
                kind="agent", inputs=step.inputs, dependencies=step.dependencies, retry_policy=step.retry_policy,
                timeout=step.timeout,
            )
            for step in output.execution_plan.steps
        ]
        return self.build_from_steps(
            name=output.goal, description=output.reasoning_summary, steps=steps, tags=tags,
        )
