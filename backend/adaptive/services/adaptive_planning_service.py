"""AdaptivePlanningService: the only public entry point for adaptive planning.

``optimize()``/``explain()``/``history()``/``statistics()``/``export()`` —
nothing outside ``backend/adaptive/`` should build a ``PlanningContext``/
``OptimizationResult`` directly. Deliberately holds **no store of its
own**, mirroring ``ReflectionService`` exactly (see that class's own
docstring for the reasoning): every ``OptimizationResult`` is persisted
as one ``MemoryType.ADAPTIVE_PLAN`` memory via the existing
``MemoryService``, with ``optimization_id`` literally being the
``MemoryItem.memory_id`` it's stored under.

``explain()`` does the real work (gather history, run the three
optimizer modules, build the result) without any side effect;
``optimize()`` calls ``explain()`` then remembers the result — so the
two REST endpoints (`/adaptive/explain` for a side-effect-free preview,
`/adaptive/optimize` for the real, remembered pass) share one
implementation, never two.

This is deterministic execution reflection extended one step further:
every ``OptimizationDecision`` traces back to a specific count in
``PlanningContext``, itself built from ``ReflectionService.list_all()``
(reflections) and ``MemoryService.search()`` (collaboration/dataset/
report/visualization memories) — no machine learning, no AI call.
"""

import time
from datetime import datetime
from typing import Any, Literal

from backend.adaptive.analyzers.collaboration_patterns import (
    analyze_collaboration_patterns,
)
from backend.adaptive.analyzers.execution_patterns import analyze_execution_patterns
from backend.adaptive.analyzers.reflection_patterns import analyze_reflection_patterns
from backend.adaptive.analyzers.tool_patterns import analyze_tool_patterns
from backend.adaptive.exceptions import OptimizationNotFoundError
from backend.adaptive.exporters.json_exporter import JSONOptimizationExporter
from backend.adaptive.exporters.markdown_exporter import MarkdownOptimizationExporter
from backend.adaptive.models.optimization_result import (
    OptimizationDecisionCategory,
    OptimizationResult,
)
from backend.adaptive.models.optimization_statistics import OptimizationStatistics
from backend.adaptive.models.planning_context import PlanningContext
from backend.adaptive.optimizer.approval_optimizer import generate_approval_decisions
from backend.adaptive.optimizer.execution_optimizer import optimize_execution_order
from backend.adaptive.optimizer.planner_optimizer import optimize_plan_steps
from backend.memory.exceptions import MemoryItemNotFoundError
from backend.memory.models.memory_query import MemoryQuery
from backend.memory.models.memory_reference import MemoryReference
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.observability.context import current_agent_name
from backend.observability.models.tool_trace import ToolTrace
from backend.observability.services.observability_service import ObservabilityService
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.plan import ExecutionPlan
from backend.reflection.services.reflection_service import ReflectionService
from backend.utils.time import utc_now

_ESTIMATED_SECONDS_PER_SKIPPED_STEP_FLOOR_MS = 0.0


class AdaptivePlanningService:
    """Gathers historical evidence and deterministically optimizes one ExecutionPlan."""

    def __init__(
        self,
        memory_service: MemoryService,
        reflection_service: ReflectionService,
        observability_service: ObservabilityService | None = None,
    ) -> None:
        self._memory_service = memory_service
        self._reflection_service = reflection_service
        self._observability_service = observability_service

    def explain(self, plan: ExecutionPlan, session_id: str | None = None) -> OptimizationResult:
        """Analyze ``plan`` against historical evidence and return the (unstored) result."""
        start_time, start = utc_now(), time.perf_counter()

        context = self._build_planning_context(plan, session_id)

        optimized_plan, planner_decisions = optimize_plan_steps(plan, context)
        optimized_plan, execution_decisions = optimize_execution_order(optimized_plan, context)
        approval_decisions = generate_approval_decisions(context)
        decisions = [*planner_decisions, *execution_decisions, *approval_decisions]

        execution_savings = self._estimate_execution_savings(plan, optimized_plan, context)
        approval_savings = sum(1 for d in decisions if d.category == OptimizationDecisionCategory.APPROVAL_REDUCTION)
        parallelism_improved = any(d.category == OptimizationDecisionCategory.REORDER for d in decisions)

        result = OptimizationResult(
            optimization_id="",
            plan_id=plan.plan_id,
            session_id=session_id,
            original_plan=plan,
            optimized_plan=optimized_plan,
            decisions=decisions,
            planning_context=context,
            execution_savings_estimate_seconds=execution_savings,
            approval_savings_estimate=approval_savings,
            parallelism_improved=parallelism_improved,
            generated_at=utc_now(),
        )

        self._trace("adaptive.explain", start_time, start, ExecutionStatus.COMPLETED)
        return result

    def optimize(self, plan: ExecutionPlan, session_id: str | None = None) -> OptimizationResult:
        """Analyze ``plan``, remember the result as a MemoryType.ADAPTIVE_PLAN memory, and return it."""
        start_time, start = utc_now(), time.perf_counter()

        result = self.explain(plan, session_id)

        applied_count = sum(1 for d in result.decisions if d.applied)
        memory_item = self._memory_service.remember(
            title=f"Adaptive optimization: {plan.goal or plan.plan_id}",
            summary=f"{len(result.decisions)} decision(s), {applied_count} applied to the plan directly.",
            memory_type=MemoryType.ADAPTIVE_PLAN,
            scope=MemoryScope.PROJECT,
            content=result.model_dump(mode="json"),
            importance=0.5,
            tags=["adaptive"],
            references=[MemoryReference(reference_type="plan", reference_id=plan.plan_id)],
            metadata={"session_id": session_id},
        )
        result = result.model_copy(update={"optimization_id": memory_item.memory_id})

        self._trace("adaptive.optimize", start_time, start, ExecutionStatus.COMPLETED)
        return result

    def history(self) -> list[OptimizationResult]:
        """Every stored optimization, most recently generated first."""
        search_result = self._memory_service.search(MemoryQuery(memory_type=MemoryType.ADAPTIVE_PLAN))
        return [self._to_result(item.memory_id, item.content) for item in search_result.items]

    def statistics(self) -> OptimizationStatistics:
        """Aggregate counts/averages across every stored optimization."""
        optimizations = self.history()
        if not optimizations:
            return OptimizationStatistics()

        by_category: dict[str, int] = {}
        applied_count = 0
        for optimization in optimizations:
            for decision in optimization.decisions:
                by_category[decision.category.value] = by_category.get(decision.category.value, 0) + 1
                if decision.applied:
                    applied_count += 1

        total_decisions = sum(len(o.decisions) for o in optimizations)
        return OptimizationStatistics(
            total_optimizations=len(optimizations),
            total_decisions=total_decisions,
            applied_decision_count=applied_count,
            by_category=by_category,
            average_decisions_per_optimization=total_decisions / len(optimizations),
            total_estimated_execution_savings_seconds=sum(
                o.execution_savings_estimate_seconds for o in optimizations
            ),
            total_estimated_approval_savings=sum(o.approval_savings_estimate for o in optimizations),
        )

    def export(self, optimization_id: str, export_format: Literal["json", "markdown"]) -> str:
        """Export one optimization as JSON or Markdown."""
        result = self._get(optimization_id)
        if export_format == "json":
            return JSONOptimizationExporter().export(result)
        return MarkdownOptimizationExporter().export(result)

    def _get(self, optimization_id: str) -> OptimizationResult:
        try:
            item = self._memory_service.recall(optimization_id)
        except MemoryItemNotFoundError as exc:
            raise OptimizationNotFoundError(f"No optimization found for '{optimization_id}'.") from exc
        if item.memory_type != MemoryType.ADAPTIVE_PLAN:
            raise OptimizationNotFoundError(f"No optimization found for '{optimization_id}'.")
        return self._to_result(item.memory_id, item.content)

    def _to_result(self, memory_id: str, content: dict[str, Any]) -> OptimizationResult:
        return OptimizationResult.model_validate({**content, "optimization_id": memory_id})

    def _build_planning_context(self, plan: ExecutionPlan, session_id: str | None) -> PlanningContext:
        reflections = self._reflection_service.list_all()
        collaboration_memories = [
            item for item in self._memory_service.list_all() if item.memory_type == MemoryType.COLLABORATION
        ]

        return PlanningContext(
            session_id=session_id,
            goal=plan.goal,
            reflection_patterns=analyze_reflection_patterns(reflections),
            execution_patterns=analyze_execution_patterns(reflections),
            collaboration_patterns=analyze_collaboration_patterns(collaboration_memories),
            tool_patterns=analyze_tool_patterns(self._memory_service, reflections),
        )

    def _estimate_execution_savings(
        self, original: ExecutionPlan, optimized: ExecutionPlan, context: PlanningContext
    ) -> float:
        removed_count = len(original.steps) - len(optimized.steps)
        if removed_count <= 0:
            return _ESTIMATED_SECONDS_PER_SKIPPED_STEP_FLOOR_MS
        average_tool_duration_ms = context.execution_patterns.get("average_tool_duration_ms", 0.0)
        return round((removed_count * average_tool_duration_ms) / 1000.0, 2)

    def _trace(self, operation_name: str, start_time: datetime, start: float, status: ExecutionStatus) -> None:
        if self._observability_service is None:
            return
        self._observability_service.record_tool_trace(
            ToolTrace(
                tool_name=operation_name,
                agent_name=current_agent_name.get(),
                start_time=start_time,
                end_time=utc_now(),
                duration_ms=(time.perf_counter() - start) * 1000,
                status=status,
            )
        )
