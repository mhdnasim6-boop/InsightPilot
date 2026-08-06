"""export_workflow_mermaid: reuses the two existing Mermaid generators
directly — never a third Mermaid-rendering implementation.

Before any execution exists yet, ``generate_plan_mermaid()``
(``backend.planning.visualization.mermaid``, Phase 5) renders the plain
structure. Once a real execution has run, ``generate_execution_mermaid()``
(``backend.execution.services.graph_view``, Phase 27) renders the same
graph with every step's *current* status highlighted — the exact
generator ``ExecutionService.get_graph()`` itself already uses.
"""

from backend.execution.services.execution_service import ExecutionService
from backend.execution.services.graph_view import generate_execution_mermaid
from backend.planning.visualization.mermaid import generate_plan_mermaid
from backend.workflows.models.workflow import Workflow
from backend.workflows.models.workflow_execution import WorkflowExecution
from backend.workflows.planner.workflow_builder import build_execution_plan


def export_workflow_mermaid(
    workflow: Workflow, latest_execution: WorkflowExecution | None, execution_service: ExecutionService,
) -> str:
    """Render ``workflow`` as Mermaid — status-highlighted if it has a real execution."""
    if latest_execution is not None and latest_execution.execution_id is not None:
        plan = execution_service.get_plan(latest_execution.execution_id)
        state = execution_service.get(latest_execution.execution_id)
        return generate_execution_mermaid(plan, state)

    plan = build_execution_plan(
        plan_id=workflow.plan_id or workflow.workflow_id, goal=workflow.definition.name,
        steps=workflow.definition.steps, session_id=None,
    )
    return generate_plan_mermaid(plan)
