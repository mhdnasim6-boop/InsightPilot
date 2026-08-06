"""ExecutionService: the only public entry point for the DAG execution engine.

Wires ``DependencyResolver`` + ``DAGScheduler`` + ``ExecutionCheckpointStore``
+ ``ExecutionTaskRegistry`` + ``ProgressTracker`` together and owns each
execution's ``ExecutionTrace`` lifecycle exactly like ``PlanExecutor``
already does for the sequential engine (``ObservabilityService.start_trace()``/
``finalize_trace()``/``mark_status()``). This is also the seam a future
distributed/remote executor could sit behind: every method here operates
on plain ``ExecutionPlan``/``ExecutionState`` values, so swapping
``DAGScheduler`` for one that dispatches to worker processes would touch
nothing outside this file.

An additive execution path, not a replacement — ``PlanningService``/
``PlanExecutor``/``/planner/execute`` are untouched; this class is reached
only through the new ``/execution/*`` endpoints.

Deliberately holds no per-instance execution state of its own (no
``dict[execution_id, ...]`` field on ``self``) — mirroring
``FileAgentService``/every other agent service in this codebase, which
are themselves left uncached in DI because they hold no state beyond an
already-cached store. Every request rebuilds a fresh ``ExecutionService``
via DI, so anything that must survive across requests
(``ExecutionCheckpointStore``, ``ExecutionTaskRegistry``) is instead
injected as its own independently cached collaborator.

``start()``/``resume()`` run the scheduler inside an ``asyncio.Task``
tracked in ``ExecutionTaskRegistry`` by ``execution_id`` — mirroring
``ExecutionEngine``'s own ``self._tasks`` pattern exactly
(``backend.orchestration.execution.engine``) — so ``cancel()`` can
genuinely interrupt a still-in-flight batch, not just flip already-settled
state. As in ``ExecutionEngine``, cancellation is a best-effort signal:
``DAGScheduler.run()``'s ``on_checkpoint`` callback means the checkpoint
store always reflects a recent, consistent snapshot even mid-batch, but
the *fully* settled CANCELLED status is only guaranteed once the
interrupted task's own ``CancelledError`` handling below has actually
run — a caller that calls ``cancel()`` and immediately ``get()`` may
briefly still see the pre-cancel snapshot.
"""

import asyncio

from backend.execution.checkpoint.execution_checkpoint import (
    ExecutionCheckpoint,
    ExecutionCheckpointStore,
)
from backend.execution.exceptions.errors import (
    ExecutionNotFoundError,
    ExecutionNotPausedError,
)
from backend.execution.progress.progress_tracker import (
    ProgressSnapshot,
    ProgressTracker,
)
from backend.execution.scheduler.dag_scheduler import DAGScheduler
from backend.execution.scheduler.dependency_resolver import DependencyResolver
from backend.execution.services.graph_view import generate_execution_mermaid
from backend.execution.services.task_registry import ExecutionTaskRegistry
from backend.execution.state.execution_state import ExecutionState, StepExecutionState
from backend.execution.state.node_status import NodeStatus
from backend.memory.models.memory_reference import MemoryReference
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.observability.services.observability_service import ObservabilityService
from backend.planning.exceptions.errors import PlanNotReadyError
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

_TERMINAL_FOR_TRACE = frozenset({PlanStatus.COMPLETED, PlanStatus.FAILED, PlanStatus.CANCELLED})


class ExecutionService:
    """Runs a READY ExecutionPlan as a dependency-aware, parallel DAG."""

    def __init__(
        self,
        scheduler: DAGScheduler,
        checkpoint_store: ExecutionCheckpointStore,
        task_registry: ExecutionTaskRegistry,
        observability_service: ObservabilityService | None = None,
        progress_tracker: ProgressTracker | None = None,
        memory_service: MemoryService | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._checkpoint_store = checkpoint_store
        self._task_registry = task_registry
        self._observability_service = observability_service
        self._progress_tracker = progress_tracker or ProgressTracker()
        self._memory_service = memory_service

    async def start(self, plan: ExecutionPlan, session_id: str | None = None) -> ExecutionState:
        """Start executing ``plan`` as a DAG. Raises PlanNotReadyError if not READY."""
        if plan.status != PlanStatus.READY:
            raise PlanNotReadyError(f"Plan '{plan.plan_id}' is not ready to execute (status={plan.status.value}).")

        resolver = DependencyResolver(plan)
        execution_id = generate_id()
        now = utc_now()
        state = ExecutionState(
            execution_id=execution_id,
            plan_id=plan.plan_id,
            session_id=session_id,
            status=PlanStatus.RUNNING,
            steps={
                step.step_id: StepExecutionState(step_id=step.step_id, node_name=step.node_name)
                for step in plan.steps
            },
            created_at=now,
            updated_at=now,
        )
        self._checkpoint(plan, state)

        trace_id = (
            self._observability_service.start_trace(plan.plan_id, session_id)
            if self._observability_service is not None
            else None
        )
        return await self._run_tracked(execution_id, plan, resolver, state, session_id, trace_id)

    async def resume(self, execution_id: str) -> ExecutionState:
        """Resume a PAUSED execution — after approval, or a policy change."""
        checkpoint = self._require_paused(execution_id)
        resolver = DependencyResolver(checkpoint.plan)

        state = self._scheduler.resume(resolver, checkpoint.state)
        self._checkpoint(checkpoint.plan, state)
        trace_id = self._trace_id_for(state.plan_id)
        return await self._run_tracked(execution_id, checkpoint.plan, resolver, state, state.session_id, trace_id)

    async def _run_tracked(
        self,
        execution_id: str,
        plan: ExecutionPlan,
        resolver: DependencyResolver,
        state: ExecutionState,
        session_id: str | None,
        trace_id: str | None,
    ) -> ExecutionState:
        def _on_checkpoint(latest: ExecutionState) -> None:
            self._checkpoint(plan, latest)

        task = asyncio.create_task(
            self._scheduler.run(resolver, state, session_id, trace_id, on_checkpoint=_on_checkpoint)
        )
        self._task_registry.register(execution_id, task)
        try:
            state = await task
        except asyncio.CancelledError:
            checkpoint = self._checkpoint_store.get(execution_id)
            state = self._scheduler.cancel(checkpoint.state if checkpoint is not None else state)
        finally:
            self._task_registry.discard(execution_id)

        self._checkpoint(plan, state)
        self._sync_trace(state, trace_id)
        self._remember_execution(state)
        return state

    def cancel(self, execution_id: str) -> ExecutionState:
        """Cancel every currently RUNNING/QUEUED/PAUSED/PENDING step. Completed steps are untouched.

        If ``execution_id`` is still genuinely in flight (a ``start()``/
        ``resume()`` call is actively awaiting its scheduler task), this
        requests real ``asyncio`` cancellation of that task — mirroring
        ``ExecutionEngine.cancel()`` exactly — and the settled CANCELLED
        state lands moments later via that awaiting call's own
        ``CancelledError`` handling. Otherwise (e.g. cancelling a plan
        that's merely PAUSED on an approval, with nothing actively
        running) this settles the checkpoint synchronously instead.
        """
        task = self._task_registry.get(execution_id)
        if task is not None and not task.done():
            task.cancel()
            checkpoint = self._checkpoint_store.get(execution_id)
            if checkpoint is not None:
                return checkpoint.state

        checkpoint = self._checkpoint_store.get(execution_id)
        if checkpoint is None:
            raise ExecutionNotFoundError(f"No execution found for '{execution_id}'.")

        state = self._scheduler.cancel(checkpoint.state)
        self._checkpoint(checkpoint.plan, state)
        trace_id = self._trace_id_for(state.plan_id)
        if trace_id is not None and self._observability_service is not None:
            self._observability_service.finalize_trace(trace_id, PlanStatus.CANCELLED)
        self._remember_execution(state)
        return state

    def get(self, execution_id: str) -> ExecutionState:
        """Fetch an execution's current state. Raises ExecutionNotFoundError if unknown."""
        return self._get_checkpoint(execution_id).state

    def get_plan(self, execution_id: str) -> ExecutionPlan:
        """Fetch the ExecutionPlan an execution is (or was) running. Raises ExecutionNotFoundError if unknown.

        Purely additive (Phase 36 — ``backend.workflows``): lets a caller
        that only holds an ``execution_id`` (e.g. after resuming an
        approval-paused execution, where no new plan was built) recover
        the originating plan without reaching into this service's own
        checkpoint store directly.
        """
        return self._get_checkpoint(execution_id).plan

    def get_progress(self, execution_id: str) -> ProgressSnapshot:
        """Fetch an execution's current progress summary."""
        return self._progress_tracker.snapshot(self.get(execution_id))

    def get_graph(self, execution_id: str) -> str:
        """Fetch an execution's plan as Mermaid, each step highlighted by its current status."""
        checkpoint = self._get_checkpoint(execution_id)
        return generate_execution_mermaid(checkpoint.plan, checkpoint.state)

    def _get_checkpoint(self, execution_id: str) -> ExecutionCheckpoint:
        checkpoint = self._checkpoint_store.get(execution_id)
        if checkpoint is None:
            raise ExecutionNotFoundError(f"No execution found for '{execution_id}'.")
        return checkpoint

    def _require_paused(self, execution_id: str) -> ExecutionCheckpoint:
        checkpoint = self._checkpoint_store.get(execution_id)
        if checkpoint is None or checkpoint.state.status != PlanStatus.PAUSED:
            raise ExecutionNotPausedError(f"Execution '{execution_id}' is not paused.")
        return checkpoint

    def _checkpoint(self, plan: ExecutionPlan, state: ExecutionState) -> None:
        self._checkpoint_store.put(
            ExecutionCheckpoint(
                execution_id=state.execution_id,
                plan_id=state.plan_id,
                plan=plan,
                state=state,
                checkpointed_at=utc_now(),
            )
        )

    def _remember_execution(self, state: ExecutionState) -> None:
        if self._memory_service is None or state.status not in _TERMINAL_FOR_TRACE:
            return
        completed = state.step_ids_with_status(NodeStatus.COMPLETED)
        failed = state.step_ids_with_status(NodeStatus.FAILED)
        self._memory_service.remember(
            title=f"Execution {state.execution_id[:8]} — {state.status.value}",
            summary=f"{len(completed)} step(s) completed, {len(failed)} failed.",
            memory_type=MemoryType.EXECUTION,
            scope=MemoryScope.PROJECT,
            content={
                "execution_id": state.execution_id,
                "plan_id": state.plan_id,
                "status": state.status.value,
                "completed_steps": completed,
                "failed_steps": failed,
            },
            tags=["execution"],
            references=[MemoryReference(reference_type="plan", reference_id=state.plan_id)],
            metadata={"session_id": state.session_id},
        )

    def _trace_id_for(self, plan_id: str) -> str | None:
        if self._observability_service is None:
            return None
        return self._observability_service.trace_id_for_plan(plan_id)

    def _sync_trace(self, state: ExecutionState, trace_id: str | None) -> None:
        if self._observability_service is None or trace_id is None:
            return
        if state.status in _TERMINAL_FOR_TRACE:
            self._observability_service.finalize_trace(trace_id, state.status)
        elif state.status == PlanStatus.PAUSED:
            self._observability_service.mark_status(trace_id, PlanStatus.PAUSED)
