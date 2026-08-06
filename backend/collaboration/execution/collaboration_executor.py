"""CollaborationExecutor: drives a collaboration session to completion by
repeatedly handing dependency-ready "waves" of subtasks to the existing
``ExecutionService``.

This is the seam where "structured collaboration" meets "the existing
execution engine": each wave is a small, READY ``ExecutionPlan`` of
mutually-independent subtasks, submitted through
``ExecutionService.start()``/``resume()`` completely unmodified — so
intra-wave parallelism (``DAGScheduler``) and per-node approval pausing
(``ApprovalService``) both come for free. Between waves,
``SubTaskManager``/``CollaborationCoordinator`` route completed
producers' artifacts into the next wave's inputs and check for dynamic
follow-up requests, expanding the task graph without ``DAGScheduler``
or ``ExecutionService`` ever needing to know a "collaboration" exists.
"""

from backend.collaboration.coordinator.collaboration_coordinator import (
    CollaborationCoordinator,
)
from backend.collaboration.exceptions import CollaborationNotPausedError
from backend.collaboration.execution.subtask_manager import SubTaskManager
from backend.collaboration.models.collaboration_task import CollaborationTask, SubTask
from backend.execution.services.execution_service import ExecutionService
from backend.execution.state.node_status import NodeStatus
from backend.planning.models.enums import PlanStatus
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class CollaborationExecutor:
    """Runs, resumes, and cancels a collaboration session's wave-by-wave execution."""

    def __init__(
        self,
        coordinator: CollaborationCoordinator,
        subtask_manager: SubTaskManager,
        execution_service: ExecutionService,
    ) -> None:
        self._coordinator = coordinator
        self._subtask_manager = subtask_manager
        self._execution_service = execution_service

    async def run(self, collaboration_id: str) -> CollaborationTask:
        """Run every currently-ready (and dynamically spawned) subtask to completion or a pause."""
        task = self._coordinator.get(collaboration_id)
        task = self._coordinator.update(task.model_copy(update={"status": PlanStatus.RUNNING, "updated_at": utc_now()}))
        return await self._drive(task)

    async def resume(self, collaboration_id: str) -> CollaborationTask:
        """Resume a PAUSED collaboration's currently-paused wave, then keep driving."""
        task = self._coordinator.get(collaboration_id)
        if task.active_execution_id is None or task.status != PlanStatus.PAUSED:
            raise CollaborationNotPausedError(f"Collaboration '{collaboration_id}' is not paused.")

        state = await self._execution_service.resume(task.active_execution_id)
        task, _ = self._subtask_manager.apply_execution_state(collaboration_id, task, state)
        if state.status == PlanStatus.PAUSED:
            return self._coordinator.update(task)

        task = self._coordinator.update(task.model_copy(update={"active_execution_id": None}))
        return await self._drive(task)

    def cancel(self, collaboration_id: str) -> CollaborationTask:
        """Cancel a collaboration outright — its active wave (if any) and every remaining subtask."""
        task = self._coordinator.get(collaboration_id)
        if task.active_execution_id is not None:
            self._execution_service.cancel(task.active_execution_id)
        for subtask_id in task.subtask_ids_with_status(NodeStatus.PENDING, NodeStatus.PAUSED):
            task = self._coordinator.receive_result(collaboration_id, subtask_id, NodeStatus.CANCELLED, None, None)
        return self._coordinator.finish(collaboration_id, PlanStatus.CANCELLED)

    async def _drive(self, task: CollaborationTask) -> CollaborationTask:
        while True:
            ready = self._coordinator.runnable_subtasks(task)
            if not ready:
                break

            plan = self._subtask_manager.build_wave_plan(task, ready, generate_id())
            state = await self._execution_service.start(plan, task.session_id)
            task, settled = self._subtask_manager.apply_execution_state(task.collaboration_id, task, state)

            if state.status == PlanStatus.PAUSED:
                return self._coordinator.update(
                    task.model_copy(update={"active_execution_id": state.execution_id, "status": PlanStatus.PAUSED})
                )

            for subtask in settled:
                self._maybe_spawn_followup(task, subtask)
            task = self._coordinator.get(task.collaboration_id)

        task = self._cancel_unreachable(task)
        final_status = (
            PlanStatus.FAILED
            if task.subtask_ids_with_status(NodeStatus.FAILED, NodeStatus.CANCELLED)
            else PlanStatus.COMPLETED
        )
        return self._coordinator.finish(task.collaboration_id, final_status)

    def _maybe_spawn_followup(self, task: CollaborationTask, subtask: SubTask) -> None:
        followup = self._subtask_manager.detect_followup_request(subtask)
        if followup is None:
            return
        self._coordinator.spawn_subtask(
            task.collaboration_id,
            requested_by_subtask_id=subtask.subtask_id,
            assigned_agent=str(followup["agent"]),
            description=str(followup.get("description", f"Follow-up requested by {subtask.assigned_agent}")),
            inputs=dict(followup.get("inputs", {})),
            reason=str(followup.get("reason", "")),
        )

    def _cancel_unreachable(self, task: CollaborationTask) -> CollaborationTask:
        """A subtask still PENDING once no more waves are ready is blocked forever — mark it CANCELLED."""
        for subtask_id in task.subtask_ids_with_status(NodeStatus.PENDING):
            task = self._coordinator.receive_result(
                task.collaboration_id, subtask_id, NodeStatus.CANCELLED, None, "Unreachable: a dependency never completed."
            )
        return task
