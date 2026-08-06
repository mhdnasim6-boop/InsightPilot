"""WorkflowEngine: the highest orchestration layer — validates, optimizes,
and runs a Workflow entirely by delegating to the real
PlanValidator/PlanOptimizer (via WorkflowValidator/WorkflowOptimizer),
AdaptivePlanningService, and ExecutionService. No execution logic of its
own; this class only sequences existing calls and records the outcome.

Pause/resume reuse the *two* real pause mechanisms that already exist,
distinguished by ``WorkflowExecution.pause_reason``:

- ``"approval"`` — the underlying DAG genuinely paused itself at an
  approval gate (``DAGScheduler``'s own, existing behavior). Resuming
  calls the real ``ExecutionService.resume(execution_id)`` — the exact
  mechanism Phase 27 built for this, continuing the *same* execution.
- ``"manual"`` — a caller asked to pause a still-running workflow.
  ``DAGScheduler`` has no voluntary-pause primitive (only approval-driven
  pausing exists), so this is honestly built from what *does* exist:
  ``ExecutionService.cancel()`` halts the in-flight DAG; resuming rebuilds
  a fresh ``ExecutionPlan`` containing only the steps that never
  completed and starts a *new* execution via ``ExecutionService.start()``
  — the existing dependency-ignoring behavior of ``topological_order()``
  (dependencies on since-removed, already-completed steps are silently
  dropped) makes this a correct, non-duplicative continuation, not a new
  scheduling algorithm.
"""

from backend.execution.services.execution_service import ExecutionService
from backend.execution.state.execution_state import ExecutionState
from backend.execution.state.node_status import NodeStatus
from backend.observability.services.observability_service import ObservabilityService
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.reflection.services.reflection_service import ReflectionService
from backend.utils.ids import generate_id
from backend.utils.time import utc_now
from backend.workflows.coordination.execution_coordinator import ExecutionCoordinator
from backend.workflows.exceptions import (
    WorkflowNotPausedError,
    WorkflowNotReadyError,
    WorkflowValidationError,
)
from backend.workflows.execution.workflow_scheduler import WorkflowScheduler
from backend.workflows.models.workflow import Workflow
from backend.workflows.models.workflow_execution import WorkflowExecution
from backend.workflows.models.workflow_status import WorkflowStatus
from backend.workflows.planner.workflow_optimizer import WorkflowOptimizer
from backend.workflows.planner.workflow_validator import WorkflowValidator

_TERMINAL = frozenset({PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.CANCELLED})
_TERMINAL_WORKFLOW_STATUSES = frozenset({WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED})


class WorkflowEngine:
    """Runs a Workflow end-to-end through the real planning/adaptive/execution engines."""

    def __init__(
        self,
        execution_coordinator: ExecutionCoordinator,
        validator: WorkflowValidator,
        optimizer: WorkflowOptimizer,
        execution_service: ExecutionService,
        scheduler: WorkflowScheduler,
        observability_service: ObservabilityService | None = None,
        reflection_service: ReflectionService | None = None,
    ) -> None:
        self._execution_coordinator = execution_coordinator
        self._validator = validator
        self._optimizer = optimizer
        self._execution_service = execution_service
        self._scheduler = scheduler
        self._observability_service = observability_service
        self._reflection_service = reflection_service

    async def execute(self, workflow: Workflow, session_id: str | None = None) -> tuple[Workflow, WorkflowExecution]:
        """Validate, optimize, and run ``workflow`` via the real ExecutionService."""
        structural_issues = self._validator.validate_structure(workflow)
        if structural_issues:
            raise WorkflowValidationError("; ".join(structural_issues))

        plan = self._execution_coordinator.prepare(
            workflow.plan_id or generate_id(), workflow.definition.name, workflow.definition.steps, session_id,
        )
        return await self._run_plan(workflow, plan, session_id)

    async def _run_plan(
        self, workflow: Workflow, plan: ExecutionPlan, session_id: str | None,
    ) -> tuple[Workflow, WorkflowExecution]:
        plan, validation_result = await self._validator.validate_plan(plan)
        if not validation_result.is_valid:
            raise WorkflowValidationError("; ".join(issue.message for issue in validation_result.errors))

        optimization_result = self._optimizer.adaptive_optimize(plan, session_id)
        plan = self._optimizer.structural_optimize(optimization_result.optimized_plan)

        state = await self._scheduler.run(lambda: self._execution_service.start(plan, session_id))

        workflow_execution = self._build_execution(workflow.workflow_id, plan.plan_id, state, session_id)
        workflow_execution = workflow_execution.model_copy(update={"optimization_id": optimization_result.optimization_id})
        workflow_execution = await self._maybe_reflect(workflow_execution, plan, state)

        updated_workflow = workflow.model_copy(
            update={"status": WorkflowStatus(state.status.value), "plan_id": plan.plan_id, "updated_at": utc_now()}
        )
        return updated_workflow, workflow_execution

    async def pause(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Voluntarily pause a running execution. See this module's own docstring for why
        this uses ExecutionService.cancel() rather than a new pause primitive.

        A no-op (returns ``execution`` unchanged) if it has already reached a
        terminal status — ``ExecutionService.cancel()`` would otherwise try to
        finalize an already-finalized ObservabilityService trace a second
        time and raise. A real, plausible race (not just a test artifact):
        the caller's own "pause" click can easily lose a race against a
        fast-completing execution.
        """
        if execution.status in _TERMINAL_WORKFLOW_STATUSES:
            return execution
        if execution.execution_id is None:
            raise WorkflowNotReadyError(f"Workflow execution '{execution.workflow_execution_id}' has not started yet.")
        state = self._execution_service.cancel(execution.execution_id)
        return execution.model_copy(
            update={
                "status": WorkflowStatus.PAUSED, "pause_reason": "manual",
                "completed_steps": state.step_ids_with_status(NodeStatus.COMPLETED),
                "pending_steps": [
                    step_id for step_id, step in state.steps.items()
                    if step.status not in {NodeStatus.COMPLETED, NodeStatus.CANCELLED}
                ],
                "updated_at": utc_now(),
            }
        )

    async def resume(
        self, execution: WorkflowExecution, workflow: Workflow, session_id: str | None = None,
    ) -> tuple[Workflow, WorkflowExecution]:
        """Resume a paused execution — via ExecutionService.resume() for an approval-driven
        pause, or by starting a fresh execution over the remaining steps for a manual one."""
        if execution.status != WorkflowStatus.PAUSED:
            raise WorkflowNotPausedError(f"Workflow execution '{execution.workflow_execution_id}' is not paused.")

        if execution.pause_reason == "approval":
            execution_id = execution.execution_id
            if execution_id is None:
                raise WorkflowNotReadyError(f"Workflow execution '{execution.workflow_execution_id}' has no underlying execution.")
            state = await self._scheduler.run(lambda: self._execution_service.resume(execution_id))
            plan = self._execution_service.get_plan(execution_id)
            workflow_execution = self._build_execution(workflow.workflow_id, plan.plan_id, state, session_id)
            workflow_execution = await self._maybe_reflect(workflow_execution, plan, state)
            updated_workflow = workflow.model_copy(
                update={"status": WorkflowStatus(state.status.value), "updated_at": utc_now()}
            )
            return updated_workflow, workflow_execution

        remaining_ids = set(execution.pending_steps) | set(execution.failed_steps)
        remaining_steps = [step for step in workflow.definition.steps if step.step_id in remaining_ids]
        if not remaining_steps:
            completed_execution = execution.model_copy(
                update={"status": WorkflowStatus.COMPLETED, "updated_at": utc_now(), "completed_at": utc_now()}
            )
            return workflow.model_copy(update={"status": WorkflowStatus.COMPLETED, "updated_at": utc_now()}), completed_execution

        plan = self._execution_coordinator.prepare(generate_id(), workflow.definition.name, remaining_steps, session_id)
        return await self._run_plan(workflow, plan, session_id)

    def cancel(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Cancel a running or paused execution outright. A no-op if already terminal —
        see ``pause()``'s own docstring for why."""
        if execution.status in _TERMINAL_WORKFLOW_STATUSES:
            return execution
        if execution.execution_id is None:
            raise WorkflowNotReadyError(f"Workflow execution '{execution.workflow_execution_id}' has not started yet.")
        state = self._execution_service.cancel(execution.execution_id)
        return execution.model_copy(
            update={
                "status": WorkflowStatus.CANCELLED, "pause_reason": None,
                "completed_steps": state.step_ids_with_status(NodeStatus.COMPLETED),
                "updated_at": utc_now(), "completed_at": utc_now(),
            }
        )

    def _build_execution(
        self, workflow_id: str, plan_id: str, state: ExecutionState, session_id: str | None,
    ) -> WorkflowExecution:
        now = utc_now()
        trace_id = self._observability_service.trace_id_for_plan(plan_id) if self._observability_service else None
        return WorkflowExecution(
            workflow_execution_id=generate_id(), workflow_id=workflow_id, plan_id=plan_id,
            execution_id=state.execution_id, session_id=session_id, status=WorkflowStatus(state.status.value),
            pause_reason="approval" if state.status == PlanStatus.PAUSED else None, trace_id=trace_id,
            completed_steps=state.step_ids_with_status(NodeStatus.COMPLETED),
            pending_steps=state.step_ids_with_status(NodeStatus.PENDING, NodeStatus.QUEUED, NodeStatus.RUNNING),
            failed_steps=state.step_ids_with_status(NodeStatus.FAILED),
            started_at=now, updated_at=now, completed_at=now if state.status in _TERMINAL else None,
        )

    async def _maybe_reflect(
        self, execution: WorkflowExecution, plan: ExecutionPlan, state: ExecutionState,
    ) -> WorkflowExecution:
        if state.status != PlanStatus.COMPLETED or self._reflection_service is None:
            return execution
        if self._observability_service is None or execution.trace_id is None:
            return execution
        try:
            trace = self._observability_service.get_trace(execution.trace_id)
            reflection = self._reflection_service.generate(plan, trace)
        except Exception:  # noqa: BLE001 - reflection is an enrichment; it must never fail the workflow itself
            return execution
        return execution.model_copy(update={"reflection_id": reflection.reflection_id})
