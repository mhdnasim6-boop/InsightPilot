"""WorkflowValidator: workflow-level structural checks, plus delegation to
the real PlanValidator (via PlanningService.validate()) for graph-level
validation — dynamic node-name checking (against
OrchestrationService.get_graph_metadata()) included for free.
"""

from backend.planning.models.plan import ExecutionPlan
from backend.planning.validator.result import PlanValidationResult
from backend.services.planning_service import PlanningService
from backend.workflows.models.workflow import Workflow


class WorkflowValidator:
    """Structural workflow checks + delegation to the real PlanValidator."""

    def __init__(self, planning_service: PlanningService) -> None:
        self._planning_service = planning_service

    def validate_structure(self, workflow: Workflow) -> list[str]:
        """Workflow-level checks with no existing analog (name/step-count/step-kind) —
        every dependency/cycle/node-name check happens in ``validate_plan()`` instead."""
        issues: list[str] = []
        if not workflow.definition.name.strip():
            issues.append("Workflow name must not be empty.")
        if not workflow.definition.steps:
            issues.append("Workflow must have at least one step.")
        for step in workflow.definition.steps:
            if step.kind != "agent":
                issues.append(
                    f"Step '{step.step_id}' has kind='{step.kind}' — only 'agent' steps are executable today."
                )
        return issues

    async def validate_plan(self, plan: ExecutionPlan) -> tuple[ExecutionPlan, PlanValidationResult]:
        """Delegate to the real PlanningService.validate() — no reimplementation."""
        return await self._planning_service.validate(plan)
