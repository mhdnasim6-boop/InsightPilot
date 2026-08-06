"""WorkflowPublisher: WorkflowStarted/Completed/Failed, ReflectionGenerated,
OptimizationGenerated.

The primary class here, ``RealtimePublishingWorkflowService``, wraps
``WorkflowService`` (its full public surface is large — creation,
validation, optimization, execution, cloning, export, statistics — but
only ``execute``/``resume``/``cancel`` are lifecycle-terminal calls this
phase cares about; every other method is forwarded unchanged via
``__getattr__``, so this class never has to be kept in sync with
``WorkflowService``'s own unrelated methods). Wired into
``get_workflow_service()`` (``backend.dependencies.workflows``), wrapping
the real service before it's returned — every consumer (the REST router,
``ExecutionCoordinator``, tests) transparently gets the decorated
version with no code of its own aware anything changed. ``EventType``
has no dedicated "cancelled" member (a closed, 24-member enum this phase
specifies exactly), so ``cancel()`` reports ``WORKFLOW_FAILED`` with
``data={"reason": "cancelled"}`` — visible over silently dropped, and
distinguishable via that field.

``ReflectionGenerated``/``OptimizationGenerated`` live in this same
module because both are only ever produced *from inside*
``WorkflowEngine.execute()``/``resume()`` (``ReflectionService.generate()``
via ``_maybe_reflect()``; ``WorkflowOptimizer.adaptive_optimize()`` via
``_run_plan()``) — the same workflow lifecycle this file's primary class
already observes, not a business concern of the wrapped
``ReflectionService``/``WorkflowOptimizer`` themselves.
"""

from typing import Any

from backend.adaptive.models.optimization_result import OptimizationResult
from backend.planning.models.plan import ExecutionPlan
from backend.realtime.events.event import Event
from backend.realtime.events.event_type import EventType
from backend.realtime.services.realtime_service import RealtimeService
from backend.reflection.models.reflection_result import ReflectionResult
from backend.reflection.services.reflection_service import ReflectionService
from backend.workflows.models.workflow_execution import WorkflowExecution
from backend.workflows.models.workflow_status import WorkflowStatus
from backend.workflows.planner.workflow_optimizer import WorkflowOptimizer
from backend.workflows.services.workflow_service import WorkflowService

_TERMINAL_EVENT: dict[WorkflowStatus, EventType] = {
    WorkflowStatus.COMPLETED: EventType.WORKFLOW_COMPLETED,
    WorkflowStatus.FAILED: EventType.WORKFLOW_FAILED,
}


class RealtimePublishingWorkflowService:
    """Wraps a real WorkflowService, publishing Workflow* events around execute/resume/cancel."""

    def __init__(self, inner: WorkflowService, realtime_service: RealtimeService) -> None:
        self._inner = inner
        self._realtime_service = realtime_service

    async def execute(self, workflow_id: str, session_id: str | None = None) -> WorkflowExecution:
        self._publish(EventType.WORKFLOW_STARTED, workflow_id=workflow_id)
        execution = await self._inner.execute(workflow_id, session_id)
        self._publish_terminal(execution)
        return execution

    async def resume(self, workflow_execution_id: str, session_id: str | None = None) -> WorkflowExecution:
        execution = await self._inner.resume(workflow_execution_id, session_id)
        self._publish(EventType.WORKFLOW_STARTED, workflow_id=execution.workflow_id, execution=execution)
        self._publish_terminal(execution)
        return execution

    def cancel(self, workflow_execution_id: str) -> WorkflowExecution:
        execution = self._inner.cancel(workflow_execution_id)
        self._publish(EventType.WORKFLOW_FAILED, workflow_id=execution.workflow_id, execution=execution, data={"reason": "cancelled"})
        return execution

    def _publish_terminal(self, execution: WorkflowExecution) -> None:
        event_type = _TERMINAL_EVENT.get(execution.status)
        if event_type is not None:
            self._publish(event_type, workflow_id=execution.workflow_id, execution=execution)

    def _publish(
        self,
        event_type: EventType,
        workflow_id: str,
        execution: WorkflowExecution | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        self._realtime_service.publish(
            Event(
                event_type=event_type,
                workflow_id=workflow_id,
                execution_id=execution.execution_id if execution else None,
                plan_id=execution.plan_id if execution else None,
                trace_id=execution.trace_id if execution else None,
                data=data or {},
            )
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class RealtimePublishingReflectionService:
    """Wraps a real ReflectionService, publishing ReflectionGenerated after every ``generate()``."""

    def __init__(self, inner: ReflectionService, realtime_service: RealtimeService) -> None:
        self._inner = inner
        self._realtime_service = realtime_service

    def generate(self, plan: ExecutionPlan, trace: Any, collaboration_task: Any = None, report_document: Any = None) -> ReflectionResult:
        result = self._inner.generate(plan, trace, collaboration_task, report_document)
        self._realtime_service.publish(
            Event(
                event_type=EventType.REFLECTION_GENERATED,
                plan_id=result.plan_id,
                trace_id=result.trace_id,
                data={"reflection_id": result.reflection_id},
            )
        )
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class RealtimePublishingWorkflowOptimizer:
    """Wraps a real WorkflowOptimizer, publishing OptimizationGenerated after every ``adaptive_optimize()``."""

    def __init__(self, inner: WorkflowOptimizer, realtime_service: RealtimeService) -> None:
        self._inner = inner
        self._realtime_service = realtime_service

    def adaptive_optimize(self, plan: ExecutionPlan, session_id: str | None) -> OptimizationResult:
        result = self._inner.adaptive_optimize(plan, session_id)
        self._realtime_service.publish(
            Event(
                event_type=EventType.OPTIMIZATION_GENERATED,
                plan_id=result.plan_id,
                data={
                    "optimization_id": result.optimization_id,
                    "decision_count": len(result.decisions),
                    "parallelism_improved": result.parallelism_improved,
                },
            )
        )
        return result

    def structural_optimize(self, plan: ExecutionPlan) -> ExecutionPlan:
        return self._inner.structural_optimize(plan)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
