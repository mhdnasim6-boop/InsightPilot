"""WorkflowService: the single public entry point for the Workflow Engine.

Every real computation is delegated: building/discovery to
``WorkflowBuilder``/``WorkflowDispatcher``, ordering/cycles to
``WorkflowDependencyGraph``, validation to ``WorkflowValidator`` (itself
delegating to the real ``PlanValidator``), optimization to
``WorkflowOptimizer`` (``AdaptivePlanningService`` + the real
``PlanOptimizer``), and execution/pause/resume/cancel to
``WorkflowEngine`` (the real ``ExecutionService``). This class only
stores identity (``WorkflowStore``, mirroring ``PluginRegistry``'s own
"hold state directly, no separate store class" shape) and sequences calls
— no business intelligence logic, no duplicated engine logic.
"""

from typing import Literal

from backend.approval.services.approval_service import ApprovalService
from backend.execution.services.execution_service import ExecutionService
from backend.memory.services.memory_service import MemoryService
from backend.observability.services.observability_service import ObservabilityService
from backend.utils.ids import generate_id
from backend.utils.time import utc_now
from backend.workflows.coordination.collaboration_manager import (
    WorkflowCollaborationManager,
)
from backend.workflows.coordination.dependency_graph import WorkflowDependencyGraph
from backend.workflows.coordination.execution_coordinator import ExecutionCoordinator
from backend.workflows.exceptions import (
    WorkflowExecutionNotFoundError,
    WorkflowNotFoundError,
    WorkflowValidationError,
)
from backend.workflows.execution.workflow_checkpoint import (
    WorkflowCheckpoint,
    build_workflow_checkpoint,
)
from backend.workflows.execution.workflow_dispatcher import WorkflowDispatcher
from backend.workflows.execution.workflow_engine import WorkflowEngine
from backend.workflows.exporters.json_exporter import export_workflow_json
from backend.workflows.exporters.markdown_exporter import export_workflow_markdown
from backend.workflows.exporters.mermaid_exporter import export_workflow_mermaid
from backend.workflows.models.workflow import Workflow
from backend.workflows.models.workflow_execution import WorkflowExecution
from backend.workflows.models.workflow_statistics import WorkflowStatistics
from backend.workflows.models.workflow_status import WorkflowStatus
from backend.workflows.models.workflow_step import WorkflowStep
from backend.workflows.planner.workflow_builder import WorkflowBuilder
from backend.workflows.planner.workflow_optimizer import WorkflowOptimizer
from backend.workflows.planner.workflow_validator import WorkflowValidator


class WorkflowStore:
    """Process-wide, in-memory Workflow/WorkflowExecution records — mirrors
    ``PluginRegistry``'s own "hold the dicts directly" shape exactly."""

    def __init__(self) -> None:
        self._workflows: dict[str, Workflow] = {}
        self._executions: dict[str, WorkflowExecution] = {}

    def add_workflow(self, workflow: Workflow) -> Workflow:
        self._workflows[workflow.workflow_id] = workflow
        return workflow

    def get_workflow(self, workflow_id: str) -> Workflow:
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(f"No workflow found for id '{workflow_id}'.")
        return workflow

    def list_workflows(self) -> list[Workflow]:
        return sorted(self._workflows.values(), key=lambda workflow: workflow.created_at)

    def add_execution(self, execution: WorkflowExecution) -> WorkflowExecution:
        self._executions[execution.workflow_execution_id] = execution
        return execution

    def get_execution(self, workflow_execution_id: str) -> WorkflowExecution:
        execution = self._executions.get(workflow_execution_id)
        if execution is None:
            raise WorkflowExecutionNotFoundError(f"No workflow execution found for id '{workflow_execution_id}'.")
        return execution

    def list_executions(self, workflow_id: str | None = None) -> list[WorkflowExecution]:
        executions: list[WorkflowExecution] = list(self._executions.values())
        if workflow_id is not None:
            executions = [e for e in executions if e.workflow_id == workflow_id]
        return sorted(executions, key=lambda execution: execution.started_at)


class WorkflowService:
    """Create, validate, optimize, execute, pause, resume, cancel, clone, export, and
    report statistics for Workflows — the only public entry point for this package."""

    def __init__(
        self,
        store: WorkflowStore,
        builder: WorkflowBuilder,
        validator: WorkflowValidator,
        optimizer: WorkflowOptimizer,
        engine: WorkflowEngine,
        execution_coordinator: ExecutionCoordinator,
        dependency_graph: WorkflowDependencyGraph,
        dispatcher: WorkflowDispatcher,
        collaboration_manager: WorkflowCollaborationManager,
        execution_service: ExecutionService,
        approval_service: ApprovalService,
        memory_service: MemoryService,
        observability_service: ObservabilityService | None = None,
    ) -> None:
        self._store = store
        self._builder = builder
        self._validator = validator
        self._optimizer = optimizer
        self._engine = engine
        self._execution_coordinator = execution_coordinator
        self._dependency_graph = dependency_graph
        self._dispatcher = dispatcher
        self._collaboration_manager = collaboration_manager
        self._execution_service = execution_service
        self._approval_service = approval_service
        self._memory_service = memory_service
        self._observability_service = observability_service

    # -- Create -----------------------------------------------------------------------

    def create_from_steps(
        self, name: str, description: str, steps: list[WorkflowStep], tags: list[str] | None = None,
    ) -> Workflow:
        """Create a new, DRAFT workflow from explicitly authored steps."""
        workflow = self._builder.build_from_steps(name, description, steps, tags)
        return self._store.add_workflow(workflow)

    async def create_from_objective(
        self, objective: str, session_id: str | None = None, tags: list[str] | None = None,
    ) -> Workflow:
        """Create a new, DRAFT workflow by asking the real PlannerAgent to plan ``objective``."""
        workflow = await self._builder.build_from_objective(objective, session_id, tags)
        return self._store.add_workflow(workflow)

    # -- Validate / Optimize (preview — execute() runs both internally regardless) ----

    async def validate(self, workflow_id: str) -> tuple[Workflow, list[str]]:
        """Validate a workflow's structure and dependency graph. Returns every issue found
        (empty if valid) and advances the stored workflow to VALIDATED when clean."""
        workflow = self._store.get_workflow(workflow_id)
        issues = list(self._validator.validate_structure(workflow))
        issues.extend(self._dependency_graph.validate_dependencies(workflow.definition.steps))

        if not issues:
            try:
                self._dependency_graph.order(workflow.definition.steps)
            except WorkflowValidationError as exc:
                issues.append(str(exc))

        if not issues:
            plan = self._execution_coordinator.prepare(
                workflow.plan_id or generate_id(), workflow.definition.name, workflow.definition.steps, None,
            )
            _, result = await self._validator.validate_plan(plan)
            issues.extend(issue.message for issue in result.errors)

        workflow = workflow.model_copy(
            update={"status": WorkflowStatus.VALIDATED if not issues else workflow.status, "updated_at": utc_now()}
        )
        self._store.add_workflow(workflow)
        return workflow, issues

    async def optimize(self, workflow_id: str, session_id: str | None = None) -> Workflow:
        """Run a workflow's plan through the adaptive optimizer, advancing it to READY."""
        workflow = self._store.get_workflow(workflow_id)
        plan = self._execution_coordinator.prepare(
            workflow.plan_id or generate_id(), workflow.definition.name, workflow.definition.steps, session_id,
        )
        plan, _ = await self._validator.validate_plan(plan)
        optimization_result = self._optimizer.adaptive_optimize(plan, session_id)
        plan = self._optimizer.structural_optimize(optimization_result.optimized_plan)

        workflow = workflow.model_copy(
            update={"status": WorkflowStatus.READY, "plan_id": plan.plan_id, "updated_at": utc_now()}
        )
        return self._store.add_workflow(workflow)

    # -- Execute / Pause / Resume / Cancel ---------------------------------------------

    async def execute(self, workflow_id: str, session_id: str | None = None) -> WorkflowExecution:
        """Validate, optimize, and run a workflow end-to-end via the real ExecutionService."""
        workflow = self._store.get_workflow(workflow_id)
        updated_workflow, execution = await self._engine.execute(workflow, session_id)
        self._store.add_workflow(updated_workflow)
        return self._store.add_execution(execution)

    async def pause(self, workflow_execution_id: str) -> WorkflowExecution:
        """Voluntarily pause a running workflow execution."""
        execution = self._store.get_execution(workflow_execution_id)
        paused = await self._engine.pause(execution)
        return self._store.add_execution(paused)

    async def resume(self, workflow_execution_id: str, session_id: str | None = None) -> WorkflowExecution:
        """Resume a paused workflow execution."""
        execution = self._store.get_execution(workflow_execution_id)
        workflow = self._store.get_workflow(execution.workflow_id)
        updated_workflow, resumed = await self._engine.resume(execution, workflow, session_id)
        self._store.add_workflow(updated_workflow)
        return self._store.add_execution(resumed)

    def cancel(self, workflow_execution_id: str) -> WorkflowExecution:
        """Cancel a running or paused workflow execution outright."""
        execution = self._store.get_execution(workflow_execution_id)
        cancelled = self._engine.cancel(execution)
        return self._store.add_execution(cancelled)

    # -- Clone --------------------------------------------------------------------------

    def clone(self, workflow_id: str, new_name: str | None = None) -> Workflow:
        """Create a fresh, DRAFT copy of a workflow's definition — a new workflow_id,
        version reset to 1, ``cloned_from`` pointing at the original."""
        source = self._store.get_workflow(workflow_id)
        now = utc_now()
        definition = source.definition.model_copy(update={"name": new_name or f"{source.definition.name} (copy)"})
        cloned = Workflow(
            workflow_id=generate_id(), definition=definition, status=WorkflowStatus.DRAFT,
            cloned_from=source.workflow_id, created_at=now, updated_at=now,
        )
        return self._store.add_workflow(cloned)

    # -- Export -------------------------------------------------------------------------

    def export(self, workflow_id: str, export_format: Literal["json", "markdown"]) -> str:
        """Export a workflow (+ its most recent execution, if any) as JSON or Markdown."""
        workflow = self._store.get_workflow(workflow_id)
        latest = self._latest_execution(workflow_id)
        if export_format == "json":
            return export_workflow_json(workflow, latest)
        return export_workflow_markdown(workflow, latest)

    def get_graph(self, workflow_id: str) -> str:
        """Export a workflow's dependency graph as Mermaid — status-highlighted if it has run."""
        workflow = self._store.get_workflow(workflow_id)
        latest = self._latest_execution(workflow_id)
        return export_workflow_mermaid(workflow, latest, self._execution_service)

    # -- Checkpoint -----------------------------------------------------------------------

    def get_checkpoint(self, workflow_execution_id: str) -> WorkflowCheckpoint:
        """The real, composed WorkflowCheckpoint for one execution."""
        execution = self._store.get_execution(workflow_execution_id)
        return build_workflow_checkpoint(
            execution, self._execution_service, self._approval_service, self._observability_service,
        )

    # -- Get / List -----------------------------------------------------------------------

    def get(self, workflow_id: str) -> Workflow:
        return self._store.get_workflow(workflow_id)

    def list_workflows(self) -> list[Workflow]:
        return self._store.list_workflows()

    def get_execution(self, workflow_execution_id: str) -> WorkflowExecution:
        return self._store.get_execution(workflow_execution_id)

    def list_executions(self, workflow_id: str | None = None) -> list[WorkflowExecution]:
        return self._store.list_executions(workflow_id)

    def get_latest_execution(self, workflow_id: str) -> WorkflowExecution:
        """The most recently started execution of one workflow. Raises
        WorkflowExecutionNotFoundError if it has never been executed."""
        latest = self._latest_execution(workflow_id)
        if latest is None:
            raise WorkflowExecutionNotFoundError(f"Workflow '{workflow_id}' has no executions yet.")
        return latest

    def discover_agents(self) -> list[str]:
        """Every currently discoverable agent name — proof this layer never hardcodes one."""
        return sorted(self._dispatcher.discover_agent_names())

    # -- Statistics -----------------------------------------------------------------------

    def statistics(self, workflow_id: str | None = None) -> WorkflowStatistics:
        """Aggregate counts over every known workflow/execution, or just one workflow's own."""
        workflows = self._store.list_workflows()
        if workflow_id is not None:
            workflows = [workflow for workflow in workflows if workflow.workflow_id == workflow_id]
        executions = self._store.list_executions(workflow_id)
        by_status: dict[str, int] = {}
        for workflow in workflows:
            by_status[workflow.status.value] = by_status.get(workflow.status.value, 0) + 1

        successful = sum(1 for execution in executions if execution.status == WorkflowStatus.COMPLETED)
        failed = sum(1 for execution in executions if execution.status == WorkflowStatus.FAILED)
        durations = [
            (execution.completed_at - execution.started_at).total_seconds()
            for execution in executions if execution.completed_at is not None
        ]
        average_duration = sum(durations) / len(durations) if durations else 0.0

        return WorkflowStatistics(
            total_workflows=len(workflows), total_executions=len(executions), by_status=by_status,
            successful_executions=successful, failed_executions=failed, average_duration_seconds=average_duration,
        )

    def _latest_execution(self, workflow_id: str) -> WorkflowExecution | None:
        executions = self._store.list_executions(workflow_id)
        return executions[-1] if executions else None
