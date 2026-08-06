"""SubTaskManager: translates between SubTask/CollaborationTask and the
existing ExecutionPlan/ExecutionState the DAG engine already understands.

This is the only place a SubTask ever becomes an ``ExecutionStep`` (and
back) — ``CollaborationExecutor`` never builds one itself, and
``DAGScheduler``/``ExecutionService`` are never modified to know
anything about collaboration at all.
"""

from typing import Any

from backend.collaboration.coordinator.collaboration_coordinator import (
    CollaborationCoordinator,
)
from backend.collaboration.models.collaboration_task import CollaborationTask, SubTask
from backend.execution.state.execution_state import ExecutionState
from backend.execution.state.node_status import NodeStatus
from backend.planning.models.enums import PlanStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.utils.time import utc_now

_FOLLOWUP_KEY = "requested_collaboration"


class SubTaskManager:
    """Builds per-wave ExecutionPlans and folds ExecutionState back into the task graph."""

    def __init__(self, coordinator: CollaborationCoordinator) -> None:
        self._coordinator = coordinator

    def build_wave_plan(self, task: CollaborationTask, ready: list[SubTask], plan_id: str) -> ExecutionPlan:
        """One ExecutionPlan for a wave of mutually-independent, dependency-satisfied subtasks."""
        now = utc_now()
        steps = [
            ExecutionStep(
                step_id=subtask.subtask_id,
                name=subtask.description,
                node_name=subtask.assigned_agent,
                inputs=self._coordinator.route_inputs(task, subtask),
            )
            for subtask in ready
        ]
        return ExecutionPlan(
            plan_id=plan_id,
            session_id=task.session_id,
            goal=task.goal,
            status=PlanStatus.READY,
            steps=steps,
            metadata={"collaboration_id": task.collaboration_id},
            created_at=now,
            updated_at=now,
        )

    def apply_execution_state(
        self, collaboration_id: str, task: CollaborationTask, state: ExecutionState
    ) -> tuple[CollaborationTask, list[SubTask]]:
        """Fold every changed step's status/result/error back into its SubTask.

        Returns the updated task and the subtasks that just reached a
        terminal status (COMPLETED/FAILED) this call — candidates for
        dynamic follow-up spawning.
        """
        updated_task = task
        newly_settled: list[SubTask] = []
        for step_id, step_state in state.steps.items():
            subtask = updated_task.subtasks.get(step_id)
            if subtask is None or subtask.status == step_state.status:
                continue
            updated_task = self._coordinator.receive_result(
                collaboration_id, step_id, step_state.status, step_state.result, step_state.error
            )
            if step_state.status in (NodeStatus.COMPLETED, NodeStatus.FAILED):
                newly_settled.append(updated_task.subtasks[step_id])
        return updated_task, newly_settled

    def detect_followup_request(self, subtask: SubTask) -> dict[str, Any] | None:
        """Return a subtask's own ``metadata['requested_collaboration']`` follow-up request, if any.

        Every agent Result model already carries a free-form ``metadata``
        dict — this is the one conventional key this phase introduces for
        an agent to ask the coordinator for more work, with zero change to
        any agent's own execution logic. Demonstrated in tests via stub
        AgentServices, the same way DAGScheduler's own test suite stubs
        agents rather than modifying real ones.
        """
        if subtask.result is None:
            return None
        metadata = subtask.result.get("metadata")
        if not isinstance(metadata, dict):
            return None
        request = metadata.get(_FOLLOWUP_KEY)
        if not isinstance(request, dict) or not request.get("agent"):
            return None
        return request
