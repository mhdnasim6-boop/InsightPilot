"""ReflectionService: the only public entry point for the self-reflection layer.

``generate()``/``get()``/``list_all()``/``statistics()``/``export()`` —
nothing outside ``backend/reflection/`` should build an ``ExecutionReview``
directly. Deliberately holds **no store of its own**: every reflection is
persisted as one ``MemoryType.REFLECTION`` memory via the existing
``MemoryService`` (see this class's own docstring on ``reflection_id``) —
``backend/reflection/`` has no ``stores/`` package, unlike every other
phase's own package, precisely because Memory already *is* the store.

Every input (``ExecutionTrace``, ``ExecutionPlan``, an optional
``CollaborationTask``, an optional ``ReportDocument``) is handed in by
the caller (the REST layer, which fetches each via
``ObservabilityService``/``CollaborationService``/``ReportService`` —
see ``backend/api/v1/reflection.py``) — this service only ever analyzes
already-produced data, never reaches into another service's store
itself. This is deterministic execution reflection, not reinforcement
learning: every number here is a plain function of existing trace/
approval/memory/collaboration data, and every recommendation names the
exact fact that produced it.
"""

import time
from datetime import datetime
from statistics import mean
from typing import Any, Literal

from backend.collaboration.models.collaboration_task import CollaborationTask
from backend.memory.exceptions import MemoryItemNotFoundError
from backend.memory.models.memory_query import MemoryQuery
from backend.memory.models.memory_reference import MemoryReference
from backend.memory.models.memory_scope import MemoryScope
from backend.memory.models.memory_type import MemoryType
from backend.memory.services.memory_service import MemoryService
from backend.observability.context import current_agent_name
from backend.observability.models.execution_trace import ExecutionTrace
from backend.observability.models.tool_trace import ToolTrace
from backend.observability.services.observability_service import ObservabilityService
from backend.orchestration.state.state import ExecutionStatus
from backend.planning.models.plan import ExecutionPlan
from backend.reflection.analyzers.approval_analyzer import analyze_approvals
from backend.reflection.analyzers.collaboration_analyzer import analyze_collaboration
from backend.reflection.analyzers.execution_analyzer import (
    analyze_execution,
    derive_strengths_and_weaknesses,
)
from backend.reflection.analyzers.memory_analyzer import analyze_memory
from backend.reflection.analyzers.recommendation_engine import generate_recommendations
from backend.reflection.analyzers.tool_usage_analyzer import analyze_tool_usage
from backend.reflection.exceptions import ReflectionNotFoundError
from backend.reflection.exporters.json_exporter import JSONReflectionExporter
from backend.reflection.exporters.markdown_exporter import MarkdownReflectionExporter
from backend.reflection.models.execution_review import ExecutionReview
from backend.reflection.models.improvement import Improvement
from backend.reflection.models.reflection_result import ReflectionResult
from backend.reflection.models.reflection_statistics import ReflectionStatistics
from backend.reflection.scoring.confidence_score import (
    ConfidenceScore,
    compute_confidence_score,
)
from backend.reflection.scoring.efficiency_score import (
    EfficiencyScore,
    compute_efficiency_score,
)
from backend.reflection.scoring.execution_score import (
    ExecutionScore,
    compute_execution_score,
)
from backend.reporting.models.report_document import ReportDocument
from backend.utils.ids import generate_id
from backend.utils.time import utc_now

_IMPROVEMENT_THRESHOLD = 65.0


class ReflectionService:
    """Analyzes one completed execution and stores the result as reusable knowledge."""

    def __init__(
        self,
        memory_service: MemoryService,
        observability_service: ObservabilityService | None = None,
    ) -> None:
        self._memory_service = memory_service
        self._observability_service = observability_service

    def generate(
        self,
        plan: ExecutionPlan,
        trace: ExecutionTrace,
        collaboration_task: CollaborationTask | None = None,
        report_document: ReportDocument | None = None,
    ) -> ReflectionResult:
        """Reflect on ``trace``/``plan`` (and optional collaboration/report context) and remember it."""
        start_time, start = utc_now(), time.perf_counter()

        execution_summary = analyze_execution(trace)
        tool_summary = analyze_tool_usage(trace)
        approval_summary = analyze_approvals(trace)
        memory_summary = analyze_memory(self._memory_service, plan)
        collaboration_summary = analyze_collaboration(collaboration_task)

        execution_score = compute_execution_score(trace, execution_summary)
        efficiency_score = compute_efficiency_score(trace, approval_summary)
        confidence_score = compute_confidence_score(execution_summary, memory_summary, collaboration_summary)

        strengths, weaknesses = derive_strengths_and_weaknesses(
            execution_summary, tool_summary, approval_summary, efficiency_score, confidence_score
        )
        recommendations = generate_recommendations(
            execution_summary, tool_summary, approval_summary, memory_summary, collaboration_summary
        )
        future_improvements = self._derive_future_improvements(execution_score, efficiency_score, confidence_score)

        review = ExecutionReview(
            overall_success=execution_summary["overall_success"],
            execution_score=execution_score,
            efficiency_score=efficiency_score,
            confidence_score=confidence_score,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            tool_summary=tool_summary,
            approval_summary=approval_summary,
            collaboration_summary=collaboration_summary,
            memory_summary=memory_summary,
            future_improvements=future_improvements,
        )

        result = ReflectionResult(
            reflection_id="",
            plan_id=plan.plan_id,
            session_id=trace.session_id,
            trace_id=trace.trace_id,
            collaboration_id=collaboration_task.collaboration_id if collaboration_task is not None else None,
            report_id=report_document.report_id if report_document is not None else None,
            review=review,
            generated_at=utc_now(),
        )

        memory_item = self._memory_service.remember(
            title=f"Reflection: {plan.goal or plan.plan_id}",
            summary=(
                f"Execution score {execution_score.value:.0f}/100 "
                f"({'succeeded' if review.overall_success else 'did not succeed'})."
            ),
            memory_type=MemoryType.REFLECTION,
            scope=MemoryScope.PROJECT,
            content=result.model_dump(mode="json"),
            importance=execution_score.value / 100.0,
            tags=["reflection"],
            references=[MemoryReference(reference_type="plan", reference_id=plan.plan_id)],
            metadata={"session_id": trace.session_id},
        )
        result = result.model_copy(update={"reflection_id": memory_item.memory_id})

        self._trace("reflection.generate", start_time, start, ExecutionStatus.COMPLETED)
        return result

    def get(self, reflection_id: str) -> ReflectionResult:
        """Fetch a previously generated reflection. Raises ReflectionNotFoundError if unknown."""
        try:
            item = self._memory_service.recall(reflection_id)
        except MemoryItemNotFoundError as exc:
            raise ReflectionNotFoundError(f"No reflection found for '{reflection_id}'.") from exc
        if item.memory_type != MemoryType.REFLECTION:
            raise ReflectionNotFoundError(f"No reflection found for '{reflection_id}'.")
        return self._to_result(item.memory_id, item.content)

    def list_all(self) -> list[ReflectionResult]:
        """Every stored reflection, most recently generated first."""
        result = self._memory_service.search(MemoryQuery(memory_type=MemoryType.REFLECTION))
        return [self._to_result(item.memory_id, item.content) for item in result.items]

    def statistics(self) -> ReflectionStatistics:
        """Aggregate counts/averages across every stored reflection."""
        reflections = self.list_all()
        if not reflections:
            return ReflectionStatistics()

        by_label: dict[str, int] = {}
        for reflection in reflections:
            label = reflection.review.execution_score.label
            by_label[label] = by_label.get(label, 0) + 1

        return ReflectionStatistics(
            total_reflections=len(reflections),
            success_count=sum(1 for r in reflections if r.review.overall_success),
            average_execution_score=mean(r.review.execution_score.value for r in reflections),
            average_efficiency_score=mean(r.review.efficiency_score.value for r in reflections),
            average_confidence_score=mean(r.review.confidence_score.value for r in reflections),
            total_recommendations=sum(len(r.review.recommendations) for r in reflections),
            by_label=by_label,
        )

    def export(self, reflection_id: str, export_format: Literal["json", "markdown"]) -> str:
        """Export one reflection as JSON or Markdown."""
        result = self.get(reflection_id)
        if export_format == "json":
            return JSONReflectionExporter().export(result)
        return MarkdownReflectionExporter().export(result)

    def _derive_future_improvements(
        self, execution_score: ExecutionScore, efficiency_score: EfficiencyScore, confidence_score: ConfidenceScore
    ) -> list[Improvement]:
        improvements: list[Improvement] = []
        for area, score in (
            ("execution", execution_score),
            ("efficiency", efficiency_score),
            ("confidence", confidence_score),
        ):
            if score.value < _IMPROVEMENT_THRESHOLD:
                improvements.append(
                    Improvement(
                        improvement_id=generate_id(),
                        area=area,
                        description=f"The {area} score was only {score.value:.0f}/100 ({score.label}).",
                        expected_impact=f"Addressing the top contributing factors could raise the {area} score toward 'excellent'.",
                    )
                )
        return improvements

    def _to_result(self, memory_id: str, content: dict[str, Any]) -> ReflectionResult:
        return ReflectionResult.model_validate({**content, "reflection_id": memory_id})

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
