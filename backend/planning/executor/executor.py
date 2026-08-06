"""Delegates ExecutionPlan steps to OrchestrationService.

The only bridge between planning and orchestration. No business
execution here — every step becomes one ``OrchestrationService.execute()``
call; what the underlying graph actually does is the orchestration
layer's concern, not this one's.

Since Phase 23 (Human-in-the-Loop), a step's graph run may *pause*
instead of completing — ``OrchestrationService.get_next_nodes()``
reveals this. When it does, this class consults the currently active
``ApprovalPolicy`` (via ``ApprovalPolicyService``): if the pending node
doesn't need a human decision, the run is transparently resumed inline
(the caller never sees a pause); if it does, an ``ExecutionApproval`` is
requested (via ``ApprovalService``) and the plan is returned with
``status=PAUSED`` — a dedicated lifecycle state that has existed on
``PlanStatus`` since Phase 5, unused until now.
``approval_service``/``approval_policy_service`` are optional: without
them, this class behaves exactly as before this phase — every step
always runs straight through, since ``get_next_nodes()`` only ever
returns a non-empty tuple when the compiled graph actually has interrupt
points configured with a checkpointer.

Since Phase 24 (Observability & Tracing), this class also owns each
plan's ``ExecutionTrace`` lifecycle end to end: ``observability_service``
(also optional, same reasoning) starts a trace when a plan begins
executing, records one ``AgentTrace`` per step from data every agent
result already carries, refreshes the plan's approval snapshot at every
pause/resume, and finalizes the trace the moment the plan reaches a
terminal status. ``backend.observability.context.trace_context()`` is
set around every ``OrchestrationService.execute()``/``.resume()`` call
so tool calls and AI calls made many layers below (inside whatever
agent service the graph node calls) can correlate themselves back to
this trace with no parameters threaded through the intervening calls.
"""

import time
from dataclasses import dataclass, field

from loguru import logger

from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.observability.context import trace_context
from backend.observability.services.observability_service import ObservabilityService
from backend.orchestration.nodes.approval_node import APPROVAL_NODE_PREFIX
from backend.orchestration.state.state import InsightPilotState
from backend.planning.events.bus import PlanEventBus
from backend.planning.events.events import (
    PlanCompleted,
    PlanFailed,
    PlanPaused,
    PlanResumed,
    PlanStarted,
    StepCompleted,
    StepStarted,
)
from backend.planning.exceptions.errors import PlanNotPausedError, PlanNotReadyError
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.services.orchestration_service import OrchestrationService
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


@dataclass
class _PausedExecution:
    """Bookkeeping needed to resume a plan whose step loop stopped partway through."""

    order: list[str]
    steps_by_id: dict[str, ExecutionStep]
    running_plan: ExecutionPlan
    completed_steps: list[ExecutionStep] = field(default_factory=list)
    step_index: int = 0
    execution_id: str = ""
    trace_id: str | None = None


class PlanExecutor:
    """Runs a READY ExecutionPlan's steps, in dependency order, via OrchestrationService."""

    def __init__(
        self,
        event_bus: PlanEventBus | None = None,
        approval_service: ApprovalService | None = None,
        approval_policy_service: ApprovalPolicyService | None = None,
        observability_service: ObservabilityService | None = None,
    ) -> None:
        self._event_bus = event_bus or PlanEventBus()
        self._approval_service = approval_service
        self._approval_policy_service = approval_policy_service
        self._observability_service = observability_service
        self._plans: dict[str, ExecutionPlan] = {}
        self._paused: dict[str, _PausedExecution] = {}

    async def execute(
        self,
        plan: ExecutionPlan,
        orchestration_service: OrchestrationService,
        execution_order: list[str] | None = None,
    ) -> ExecutionPlan:
        """Execute every step of ``plan``, in ``execution_order`` (or declaration order).

        Returns a plan with ``status=PAUSED`` (not COMPLETED) if a step's
        run stops at an approval gate the active policy requires a human
        decision for — see ``resume()``/``reject()``/``cancel()``.
        """
        if plan.status != PlanStatus.READY:
            raise PlanNotReadyError(f"Plan '{plan.plan_id}' is not ready to execute (status={plan.status.value}).")

        order = execution_order or [step.step_id for step in plan.steps]
        steps_by_id = {step.step_id: step for step in plan.steps}

        running_plan = plan.model_copy(
            update={"status": PlanStatus.RUNNING, "execution_id": generate_id(), "updated_at": utc_now()}
        )
        self._plans[plan.plan_id] = running_plan
        await self._event_bus.emit(PlanStarted(plan_id=plan.plan_id, timestamp=utc_now()))

        trace_id = (
            self._observability_service.start_trace(plan.plan_id, plan.session_id)
            if self._observability_service is not None
            else None
        )
        pending = _PausedExecution(order=order, steps_by_id=steps_by_id, running_plan=running_plan, trace_id=trace_id)
        return await self._run_loop(plan.plan_id, orchestration_service, pending)

    async def resume(self, plan_id: str, orchestration_service: OrchestrationService) -> ExecutionPlan:
        """Resume a plan that's currently PAUSED — after approval, or a policy change."""
        pending = self._require_paused(plan_id)
        step_id = pending.order[pending.step_index]
        step = pending.steps_by_id[step_id]

        await self._event_bus.emit(PlanResumed(plan_id=plan_id, timestamp=utc_now(), step_id=step_id))
        if self._approval_service is not None:
            self._approval_service.record_resumed(plan_id, step_id=step_id)

        start = time.perf_counter()
        with trace_context(pending.trace_id):
            result_state = await orchestration_service.resume(pending.execution_id)
        step_result, paused = await self._settle(
            plan_id, step, pending.execution_id, result_state, orchestration_service, start, pending.trace_id
        )
        pending.completed_steps[-1] = step_result
        self._record_observability(pending.trace_id, plan_id, step, step_result)

        if paused:
            if self._observability_service is not None and pending.trace_id is not None:
                self._observability_service.mark_status(pending.trace_id, PlanStatus.PAUSED)
            self._paused[plan_id] = pending
            paused_plan = pending.running_plan.model_copy(
                update={"status": PlanStatus.PAUSED, "steps": pending.completed_steps, "updated_at": utc_now()}
            )
            self._plans[plan_id] = paused_plan
            return paused_plan

        pending.step_index += 1
        return await self._run_loop(plan_id, orchestration_service, pending)

    def reject(self, plan_id: str, reason: str | None = None) -> ExecutionPlan:
        """Reject a plan's currently PAUSED execution — the plan can never resume from here."""
        pending = self._require_paused(plan_id)
        plan = self._plans[plan_id]
        failed_plan = plan.model_copy(
            update={
                "status": PlanStatus.FAILED,
                "steps": pending.completed_steps,
                "metadata": {**plan.metadata, "rejection_reason": reason} if reason else plan.metadata,
                "updated_at": utc_now(),
            }
        )
        self._plans[plan_id] = failed_plan
        del self._paused[plan_id]
        self._finalize_trace(pending.trace_id, plan_id, PlanStatus.FAILED)
        return failed_plan

    def cancel(self, plan_id: str, orchestration_service: OrchestrationService | None = None) -> ExecutionPlan:
        """Cancel a plan's currently PAUSED (or still-RUNNING) execution outright."""
        plan = self._plans.get(plan_id)
        if plan is None or plan.status not in (PlanStatus.PAUSED, PlanStatus.RUNNING):
            raise PlanNotPausedError(f"Plan '{plan_id}' has no active execution to cancel.")

        pending = self._paused.get(plan_id)
        if pending is not None and orchestration_service is not None:
            orchestration_service.cancel(pending.execution_id)
        if self._approval_service is not None:
            step_id = pending.order[pending.step_index] if pending is not None else None
            self._approval_service.record_cancelled(plan_id, step_id=step_id)

        cancelled_plan = plan.model_copy(
            update={
                "status": PlanStatus.CANCELLED,
                "steps": pending.completed_steps if pending is not None else plan.steps,
                "updated_at": utc_now(),
            }
        )
        self._plans[plan_id] = cancelled_plan
        self._paused.pop(plan_id, None)
        trace_id = pending.trace_id if pending is not None else self._trace_id_for(plan_id)
        self._finalize_trace(trace_id, plan_id, PlanStatus.CANCELLED)
        return cancelled_plan

    def inspect(self, plan_id: str) -> ExecutionPlan | None:
        """Return the last known state for a tracked plan, or None."""
        return self._plans.get(plan_id)

    def _require_paused(self, plan_id: str) -> _PausedExecution:
        pending = self._paused.get(plan_id)
        plan = self._plans.get(plan_id)
        if pending is None or plan is None or plan.status != PlanStatus.PAUSED:
            raise PlanNotPausedError(f"Plan '{plan_id}' has no paused execution.")
        return pending

    def _trace_id_for(self, plan_id: str) -> str | None:
        if self._observability_service is None:
            return None
        return self._observability_service.trace_id_for_plan(plan_id)

    def _record_observability(
        self, trace_id: str | None, plan_id: str, step: ExecutionStep, step_result: ExecutionStep
    ) -> None:
        if self._observability_service is None or trace_id is None:
            return
        self._observability_service.record_step(trace_id, step.step_id, step_result.outputs, dict(step.inputs))
        if self._approval_service is not None:
            self._observability_service.set_approvals(trace_id, self._approval_service.list_for_plan(plan_id))

    def _finalize_trace(self, trace_id: str | None, plan_id: str, status: PlanStatus) -> None:
        if self._observability_service is None or trace_id is None:
            return
        approvals = self._approval_service.list_for_plan(plan_id) if self._approval_service is not None else None
        self._observability_service.finalize_trace(trace_id, status, approvals)

    async def _run_loop(
        self, plan_id: str, orchestration_service: OrchestrationService, pending: _PausedExecution
    ) -> ExecutionPlan:
        start = time.perf_counter()
        if self._observability_service is not None and pending.trace_id is not None:
            self._observability_service.mark_status(pending.trace_id, PlanStatus.RUNNING)
        try:
            while pending.step_index < len(pending.order):
                step_id = pending.order[pending.step_index]
                step = pending.steps_by_id[step_id]
                step_result, execution_id, paused = await self._run_step(
                    plan_id, pending.running_plan, step, orchestration_service, pending.trace_id
                )
                pending.completed_steps.append(step_result)
                pending.execution_id = execution_id
                self._record_observability(pending.trace_id, plan_id, step, step_result)

                if paused:
                    if self._observability_service is not None and pending.trace_id is not None:
                        self._observability_service.mark_status(pending.trace_id, PlanStatus.PAUSED)
                    self._paused[plan_id] = pending
                    paused_plan = pending.running_plan.model_copy(
                        update={"status": PlanStatus.PAUSED, "steps": pending.completed_steps, "updated_at": utc_now()}
                    )
                    self._plans[plan_id] = paused_plan
                    return paused_plan

                pending.step_index += 1

            duration_ms = (time.perf_counter() - start) * 1000
            final_plan = pending.running_plan.model_copy(
                update={"status": PlanStatus.COMPLETED, "steps": pending.completed_steps, "updated_at": utc_now()}
            )
            self._plans[plan_id] = final_plan
            self._paused.pop(plan_id, None)
            if self._approval_service is not None:
                self._approval_service.record_completed(plan_id)
            self._finalize_trace(pending.trace_id, plan_id, PlanStatus.COMPLETED)
            await self._event_bus.emit(
                PlanCompleted(plan_id=plan_id, timestamp=utc_now(), status=PlanStatus.COMPLETED.value, duration_ms=duration_ms)
            )
            return final_plan
        except Exception as exc:
            logger.exception("Plan '{}' failed", plan_id)
            failed_plan = pending.running_plan.model_copy(
                update={"status": PlanStatus.FAILED, "steps": pending.completed_steps, "updated_at": utc_now()}
            )
            self._plans[plan_id] = failed_plan
            self._paused.pop(plan_id, None)
            if self._observability_service is not None and pending.trace_id is not None:
                self._observability_service.record_error(pending.trace_id, str(exc))
            self._finalize_trace(pending.trace_id, plan_id, PlanStatus.FAILED)
            await self._event_bus.emit(PlanFailed(plan_id=plan_id, timestamp=utc_now(), error=str(exc)))
            raise

    async def _run_step(
        self,
        plan_id: str,
        plan: ExecutionPlan,
        step: ExecutionStep,
        orchestration_service: OrchestrationService,
        trace_id: str | None,
    ) -> tuple[ExecutionStep, str, bool]:
        await self._event_bus.emit(
            StepStarted(plan_id=plan_id, timestamp=utc_now(), step_id=step.step_id, node_name=step.node_name)
        )
        start = time.perf_counter()

        # step.node_name is recorded for future targeted dispatch, but
        # OrchestrationService doesn't yet expose "run a single named node" —
        # every step currently triggers one full run of whatever graph is
        # wired, exactly like the placeholder nodes proved the framework
        # end-to-end before any real node existed.
        execution_id = generate_id()
        state = InsightPilotState(
            session_id=plan.session_id,
            execution_id=execution_id,
            user_request=plan.user_request,
            variables=dict(step.inputs),
            metadata={"plan_id": plan_id, "step_id": step.step_id},
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        with trace_context(trace_id):
            result_state = await orchestration_service.execute(state)
        step_result, paused = await self._settle(
            plan_id, step, execution_id, result_state, orchestration_service, start, trace_id
        )
        return step_result, execution_id, paused

    async def _settle(
        self,
        plan_id: str,
        step: ExecutionStep,
        execution_id: str,
        result_state: InsightPilotState,
        orchestration_service: OrchestrationService,
        start: float,
        trace_id: str | None = None,
    ) -> tuple[ExecutionStep, bool]:
        """Resolve a just-produced state for ``execution_id`` to a settled step result.

        Auto-resumes through any interrupt the active policy doesn't
        require a human decision for; stops and requests a real
        approval the moment one does.
        """
        next_nodes = await orchestration_service.get_next_nodes(execution_id)
        while next_nodes:
            gated_node = next_nodes[0].removeprefix(APPROVAL_NODE_PREFIX)
            if self._requires_approval(gated_node):
                self._request_approval(plan_id, step.step_id, gated_node, execution_id)
                await self._event_bus.emit(
                    PlanPaused(plan_id=plan_id, timestamp=utc_now(), step_id=step.step_id, node_name=gated_node)
                )
                paused_step = step.model_copy(
                    update={"status": result_state.status, "outputs": dict(result_state.artifacts)}
                )
                return paused_step, True
            with trace_context(trace_id):
                result_state = await orchestration_service.resume(execution_id)
            next_nodes = await orchestration_service.get_next_nodes(execution_id)

        duration_ms = (time.perf_counter() - start) * 1000
        await self._event_bus.emit(
            StepCompleted(plan_id=plan_id, timestamp=utc_now(), step_id=step.step_id, duration_ms=duration_ms)
        )
        settled_step = step.model_copy(update={"status": result_state.status, "outputs": dict(result_state.artifacts)})
        return settled_step, False

    def _requires_approval(self, node_name: str) -> bool:
        if self._approval_policy_service is None:
            return False
        return self._approval_policy_service.requires_approval(node_name)

    def _request_approval(self, plan_id: str, step_id: str, node_name: str, execution_id: str) -> None:
        if self._approval_service is None:
            return
        self._approval_service.request_approval(
            plan_id=plan_id,
            step_id=step_id,
            node_name=node_name,
            execution_id=execution_id,
            reason=f"Policy requires approval before '{node_name}' runs.",
        )
