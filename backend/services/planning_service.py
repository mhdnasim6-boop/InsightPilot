"""Planning entry point.

The only object future Planner agents (and anything else) should use for
validating, optimizing, executing, exporting, or inspecting plans — never
``PlanValidator``/``PlanOptimizer``/``PlanExecutor`` directly. Delegates
actual graph execution to
``backend.services.orchestration_service.OrchestrationService``; planning
never touches LangGraph or the orchestration internals itself.
"""

from backend.planning.events.bus import PlanEventBus
from backend.planning.events.events import PlanCreated, PlanValidated
from backend.planning.exceptions.errors import PlanNotReadyError
from backend.planning.executor.executor import PlanExecutor
from backend.planning.models.enums import PlanStatus
from backend.planning.models.metrics import PlanMetrics
from backend.planning.models.plan import ExecutionPlan
from backend.planning.optimizer.base import PlanOptimizer
from backend.planning.validator.result import PlanValidationResult
from backend.planning.validator.validator import PlanValidator
from backend.planning.visualization.json_export import generate_plan_json
from backend.planning.visualization.mermaid import generate_plan_mermaid
from backend.planning.visualization.timeline import PlanTimeline, generate_plan_timeline
from backend.services.orchestration_service import OrchestrationService
from backend.utils.time import utc_now


class PlanningService:
    """Validates, optimizes, executes, exports, and inspects ExecutionPlans."""

    def __init__(
        self,
        validator: PlanValidator,
        optimizer: PlanOptimizer,
        executor: PlanExecutor,
        orchestration_service: OrchestrationService,
        event_bus: PlanEventBus,
    ) -> None:
        self._validator = validator
        self._optimizer = optimizer
        self._executor = executor
        self._orchestration_service = orchestration_service
        self._event_bus = event_bus

    async def register(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Register a newly constructed plan for tracking, emitting PlanCreated."""
        await self._event_bus.emit(PlanCreated(plan_id=plan.plan_id, timestamp=utc_now(), session_id=plan.session_id))
        return plan

    async def validate(self, plan: ExecutionPlan) -> tuple[ExecutionPlan, PlanValidationResult]:
        """Validate a plan's structure, advancing it to VALIDATED if sound."""
        known_node_names = {node.name for node in self._orchestration_service.get_graph_metadata().nodes}
        result = self._validator.validate(plan, known_node_names)

        new_status = PlanStatus.VALIDATED if result.is_valid else plan.status
        validated_plan = plan.model_copy(update={"status": new_status, "updated_at": utc_now()})

        await self._event_bus.emit(
            PlanValidated(
                plan_id=plan.plan_id, timestamp=utc_now(), is_valid=result.is_valid, issue_count=len(result.issues)
            )
        )
        return validated_plan, result

    def optimize(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Optimize a VALIDATED plan, advancing it to READY."""
        if plan.status != PlanStatus.VALIDATED:
            raise PlanNotReadyError(f"Plan '{plan.plan_id}' must be validated before it can be optimized.")
        optimized = self._optimizer.optimize(plan)
        return optimized.model_copy(update={"status": PlanStatus.READY, "updated_at": utc_now()})

    async def execute(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Execute a READY plan's steps via OrchestrationService.

        May return a plan with ``status=PAUSED`` instead of COMPLETED —
        see ``resume_execution()``/``reject_execution()``/
        ``cancel_execution()`` (Phase 23, Human-in-the-Loop).
        """
        return await self._executor.execute(plan, self._orchestration_service)

    async def resume_execution(self, plan_id: str) -> ExecutionPlan:
        """Resume a plan that's currently PAUSED at an approval gate.

        Raises ``PlanNotPausedError`` if the plan has no paused
        execution to resume.
        """
        return await self._executor.resume(plan_id, self._orchestration_service)

    def reject_execution(self, plan_id: str, reason: str | None = None) -> ExecutionPlan:
        """Reject a plan's currently PAUSED execution — it can never resume from here.

        Raises ``PlanNotPausedError`` if the plan has no paused
        execution to reject.
        """
        return self._executor.reject(plan_id, reason=reason)

    def cancel_execution(self, plan_id: str) -> ExecutionPlan:
        """Cancel a plan's currently PAUSED (or still-RUNNING) execution outright.

        Raises ``PlanNotPausedError`` if the plan has no active
        execution to cancel.
        """
        return self._executor.cancel(plan_id, self._orchestration_service)

    def export_mermaid(self, plan: ExecutionPlan) -> str:
        """Render a plan's steps and dependencies as a Mermaid flowchart."""
        return generate_plan_mermaid(plan)

    def export_json(self, plan: ExecutionPlan) -> str:
        """Serialize a plan to a JSON string."""
        return generate_plan_json(plan)

    def export_timeline(self, plan: ExecutionPlan) -> PlanTimeline:
        """Build a linear timeline view of a plan's steps."""
        return generate_plan_timeline(plan)

    def get_metrics(self, plan: ExecutionPlan) -> PlanMetrics:
        """Return a snapshot of a plan's estimate fields."""
        return PlanMetrics.from_plan(plan)

    def inspect(self, plan_id: str) -> ExecutionPlan | None:
        """Return the last known state for a tracked (executed) plan, or None."""
        return self._executor.inspect(plan_id)
