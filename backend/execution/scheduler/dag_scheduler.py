"""DAGScheduler: runs an ExecutionPlan's steps as a dependency-aware DAG —
identify runnable nodes, dispatch independent ones concurrently, unlock
downstream nodes as dependencies complete, detect completion, pause at
approval gates without blocking sibling branches.

Reuses ``ApprovalPolicyService``/``ApprovalService`` exactly as
``PlanExecutor`` already does (same ``requires_approval()``/
``request_approval()`` calls), generalized from "one node per tick" to
"every independent runnable node per tick." Reuses
``ObservabilityService`` exactly as ``PlanExecutor`` already does too:
each dispatched step's result is wrapped as the same
``{f"{node_name}_result": result}`` artifact shape
``ObservabilityService.record_step()`` already parses, so zero
observability code changes were needed for this phase.
"""

import asyncio
from collections.abc import Callable

from loguru import logger

from backend.approval.models.approval import ApprovalStatus
from backend.approval.services.approval_policy_service import ApprovalPolicyService
from backend.approval.services.approval_service import ApprovalService
from backend.execution.dispatcher.node_dispatcher import NodeDispatcher
from backend.execution.parallel.execution_pool import ExecutionPool
from backend.execution.parallel.task_group import run_concurrently
from backend.execution.scheduler.dependency_resolver import DependencyResolver
from backend.execution.state.execution_state import ExecutionState, StepExecutionState
from backend.execution.state.node_status import NodeStatus
from backend.observability.context import agent_context, trace_context
from backend.observability.services.observability_service import ObservabilityService
from backend.planning.models.enums import PlanStatus
from backend.planning.models.step import ExecutionStep
from backend.utils.time import utc_now


class DAGScheduler:
    """Runs one ExecutionState to completion (or a pause point), one tick at a time."""

    def __init__(
        self,
        dispatcher: NodeDispatcher,
        pool: ExecutionPool | None = None,
        approval_service: ApprovalService | None = None,
        approval_policy_service: ApprovalPolicyService | None = None,
        observability_service: ObservabilityService | None = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._pool = pool or ExecutionPool()
        self._approval_service = approval_service
        self._approval_policy_service = approval_policy_service
        self._observability_service = observability_service

    async def run(
        self,
        resolver: DependencyResolver,
        state: ExecutionState,
        session_id: str | None,
        trace_id: str | None = None,
        on_checkpoint: Callable[[ExecutionState], None] | None = None,
    ) -> ExecutionState:
        """Advance ``state`` until nothing more can run this cycle — finished, failed, or paused.

        ``on_checkpoint`` (if given) is called after every state
        transition — including mid-batch, before a dispatch even
        completes — so a caller running this inside a cancellable
        ``asyncio.Task`` (``ExecutionService``) always has a recent,
        consistent snapshot to fall back to if cancelled mid-flight,
        rather than only ever seeing the state as of this method's
        final return.
        """
        while True:
            state = self._cancel_unreachable(resolver, state)
            self._checkpoint(on_checkpoint, state)

            runnable = resolver.runnable_steps(state)
            if not runnable:
                break

            to_dispatch: list[ExecutionStep] = []
            for step in runnable:
                already_approved = state.steps[step.step_id].approved
                if not already_approved and self._requires_approval(step.node_name):
                    state = self._pause_step(state, step)
                else:
                    state = self._mark_queued(state, step)
                    to_dispatch.append(step)
            self._refresh_approvals(state, trace_id)
            self._checkpoint(on_checkpoint, state)

            if not to_dispatch:
                break

            state = await self._dispatch_batch(state, to_dispatch, session_id, trace_id, on_checkpoint)
            self._checkpoint(on_checkpoint, state)

        state = self._finalize_status(resolver, state)
        self._checkpoint(on_checkpoint, state)
        return state

    def _checkpoint(self, on_checkpoint: Callable[[ExecutionState], None] | None, state: ExecutionState) -> None:
        if on_checkpoint is not None:
            on_checkpoint(state)

    def resume(self, resolver: DependencyResolver, state: ExecutionState) -> ExecutionState:
        """Reconcile every PAUSED step against its approval's current decision.

        APPROVED -> back to PENDING (runnable again next ``run()``);
        REJECTED -> CANCELLED (blocks its own dependents, same as a
        FAILED ancestor does); still PENDING -> stays PAUSED.
        """
        if self._approval_service is None:
            return state
        decisions = {
            approval.step_id: approval.status for approval in self._approval_service.list_for_plan(state.plan_id)
        }
        updated_steps = dict(state.steps)
        for step_id, node in state.steps.items():
            if node.status != NodeStatus.PAUSED:
                continue
            decision = decisions.get(step_id)
            if decision == ApprovalStatus.APPROVED:
                updated_steps[step_id] = node.model_copy(update={"status": NodeStatus.PENDING, "approved": True})
            elif decision == ApprovalStatus.REJECTED:
                updated_steps[step_id] = node.model_copy(update={"status": NodeStatus.CANCELLED})
        return state.model_copy(update={"steps": updated_steps, "updated_at": utc_now()})

    def cancel(self, state: ExecutionState) -> ExecutionState:
        """Cancel every currently RUNNING/QUEUED/PAUSED step. Completed steps are untouched."""
        now = utc_now()
        updated_steps = {
            step_id: (
                node.model_copy(update={"status": NodeStatus.CANCELLED, "completed_at": now})
                if node.status in (NodeStatus.RUNNING, NodeStatus.QUEUED, NodeStatus.PAUSED, NodeStatus.PENDING)
                else node
            )
            for step_id, node in state.steps.items()
        }
        return state.model_copy(
            update={"steps": updated_steps, "status": PlanStatus.CANCELLED, "updated_at": now, "completed_at": now}
        )

    def _requires_approval(self, node_name: str) -> bool:
        if self._approval_policy_service is None:
            return False
        return self._approval_policy_service.requires_approval(node_name)

    def _pause_step(self, state: ExecutionState, step: ExecutionStep) -> ExecutionState:
        if self._approval_service is not None:
            self._approval_service.request_approval(
                plan_id=state.plan_id,
                step_id=step.step_id,
                node_name=step.node_name,
                execution_id=state.execution_id,
                reason=f"Policy requires approval before '{step.node_name}' runs.",
            )
        return self._update_step(state, step.step_id, status=NodeStatus.PAUSED)

    def _mark_queued(self, state: ExecutionState, step: ExecutionStep) -> ExecutionState:
        return self._update_step(state, step.step_id, status=NodeStatus.QUEUED)

    def _cancel_unreachable(self, resolver: DependencyResolver, state: ExecutionState) -> ExecutionState:
        unreachable = resolver.unreachable_steps(state)
        if not unreachable:
            return state
        now = utc_now()
        updated_steps = dict(state.steps)
        for step_id in unreachable:
            updated_steps[step_id] = updated_steps[step_id].model_copy(
                update={"status": NodeStatus.CANCELLED, "completed_at": now}
            )
        return state.model_copy(update={"steps": updated_steps, "updated_at": now})

    def _update_step(self, state: ExecutionState, step_id: str, **updates: object) -> ExecutionState:
        updated_steps = dict(state.steps)
        updated_steps[step_id] = updated_steps[step_id].model_copy(update=updates)
        return state.model_copy(update={"steps": updated_steps, "updated_at": utc_now()})

    async def _dispatch_batch(
        self,
        state: ExecutionState,
        steps: list[ExecutionStep],
        session_id: str | None,
        trace_id: str | None,
        on_checkpoint: Callable[[ExecutionState], None] | None = None,
    ) -> ExecutionState:
        now = utc_now()
        updated_steps = dict(state.steps)
        for step in steps:
            updated_steps[step.step_id] = updated_steps[step.step_id].model_copy(
                update={"status": NodeStatus.RUNNING, "started_at": now}
            )
        state = state.model_copy(update={"steps": updated_steps, "updated_at": utc_now()})
        self._checkpoint(on_checkpoint, state)

        coroutines = [
            self._run_one(step, session_id, state.steps[step.step_id].attempts, trace_id) for step in steps
        ]
        results = await run_concurrently(coroutines)

        updated_steps = dict(state.steps)
        for result in results:
            # _run_one() builds a fresh StepExecutionState — carry the prior
            # 'approved' flag forward so a step already cleared by a human
            # decision never loses that history once it completes/fails.
            updated_steps[result.step_id] = result.model_copy(
                update={"approved": updated_steps[result.step_id].approved}
            )
            if self._observability_service is not None:
                self._observability_service.record_step(
                    trace_id, result.step_id, {f"{result.node_name}_result": result.result or {}}, {}
                )
        return state.model_copy(update={"steps": updated_steps, "updated_at": utc_now()})

    async def _run_one(
        self, step: ExecutionStep, session_id: str | None, previous_attempts: int, trace_id: str | None
    ) -> StepExecutionState:
        retry_policy = step.retry_policy
        attempts = previous_attempts
        last_error: str | None = None
        started_at = utc_now()

        async with self._pool:
            for attempt_number in range(1, retry_policy.max_attempts + 1):
                attempts += 1
                try:
                    with trace_context(trace_id), agent_context(step.node_name):
                        result = await self._dispatcher.dispatch(step, session_id)
                    result_dict = result.model_dump(mode="json")
                    return StepExecutionState(
                        step_id=step.step_id,
                        node_name=step.node_name,
                        status=NodeStatus.COMPLETED,
                        attempts=attempts,
                        result=result_dict,
                        started_at=started_at,
                        completed_at=utc_now(),
                    )
                except Exception as exc:  # noqa: BLE001 - a step's own failure must never crash the scheduler
                    last_error = str(exc)
                    logger.exception(
                        "Step '{}' (node '{}') attempt {} failed", step.step_id, step.node_name, attempt_number
                    )
                    if attempt_number < retry_policy.max_attempts:
                        delay = retry_policy.backoff_seconds * (2 ** (attempt_number - 1))
                        if delay > 0:
                            await asyncio.sleep(delay)

        return StepExecutionState(
            step_id=step.step_id,
            node_name=step.node_name,
            status=NodeStatus.FAILED,
            attempts=attempts,
            error=last_error,
            started_at=started_at,
            completed_at=utc_now(),
        )

    def _refresh_approvals(self, state: ExecutionState, trace_id: str | None) -> None:
        if self._observability_service is None or self._approval_service is None or trace_id is None:
            return
        self._observability_service.set_approvals(trace_id, self._approval_service.list_for_plan(state.plan_id))

    def _finalize_status(self, resolver: DependencyResolver, state: ExecutionState) -> ExecutionState:
        now = utc_now()
        if resolver.is_finished(state):
            # A CANCELLED step here (as opposed to DAGScheduler.cancel()'s own
            # user-initiated path, which sets PlanStatus.CANCELLED directly)
            # only ever arises from a rejected approval propagating through
            # _cancel_unreachable() — that's a failure outcome, not a success.
            any_failed_or_cancelled = any(
                node.status in (NodeStatus.FAILED, NodeStatus.CANCELLED) for node in state.steps.values()
            )
            status = PlanStatus.FAILED if any_failed_or_cancelled else PlanStatus.COMPLETED
            return state.model_copy(update={"status": status, "updated_at": now, "completed_at": now})
        if any(node.status == NodeStatus.PAUSED for node in state.steps.values()):
            return state.model_copy(update={"status": PlanStatus.PAUSED, "updated_at": now})
        return state.model_copy(update={"status": PlanStatus.RUNNING, "updated_at": now})
