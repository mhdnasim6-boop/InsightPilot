"""Observability endpoints: list/inspect traces, execution timeline, agent/tool/AI
metrics, and trace export (JSON/Markdown/CSV).

Thin HTTP wrappers only — every endpoint here is a direct call into
``ObservabilityService``/``MetricsService``/``TraceExporter``, never a
parallel implementation. Route order matters: ``/traces/plan/{plan_id}``
is registered before ``/traces/{trace_id}`` so FastAPI matches it as a
literal path segment rather than treating "plan" as a trace_id (same
reasoning as ``/reports/templates`` vs. ``/reports/{report_id}``).
"""

from typing import Literal

from fastapi import APIRouter, Depends

from backend.dependencies.observability import (
    get_metrics_service,
    get_observability_service,
    get_trace_exporter,
)
from backend.observability.exporters.trace_exporter import TraceExporter
from backend.observability.metrics.metrics_service import MetricsService
from backend.observability.metrics.models import (
    AgentMetrics,
    AIMetrics,
    ExecutionMetricsSummary,
    ToolMetrics,
)
from backend.observability.models.execution_trace import ExecutionTrace
from backend.observability.models.export_format import TraceExportFormat
from backend.observability.models.timeline import TimelineEntry
from backend.observability.services.observability_service import ObservabilityService
from backend.observability.services.timeline import build_timeline
from backend.schemas.response import SuccessResponse

router = APIRouter(prefix="/observability")

_EXPORT_FORMATS: dict[str, TraceExportFormat] = {
    "json": TraceExportFormat.JSON,
    "markdown": TraceExportFormat.MARKDOWN,
    "csv": TraceExportFormat.CSV,
}


@router.get("/traces", response_model=SuccessResponse[list[ExecutionTrace]], summary="List execution traces")
async def list_traces(
    observability_service: ObservabilityService = Depends(get_observability_service),
) -> SuccessResponse[list[ExecutionTrace]]:
    """Every trace known so far — in-progress snapshots first, then finalized traces."""
    return SuccessResponse.ok(data=observability_service.list_traces(), message="Traces fetched.")


@router.get(
    "/traces/plan/{plan_id}", response_model=SuccessResponse[ExecutionTrace], summary="Get a plan's execution trace"
)
async def get_trace_for_plan(
    plan_id: str, observability_service: ObservabilityService = Depends(get_observability_service)
) -> SuccessResponse[ExecutionTrace]:
    """Fetch the trace for a plan_id. Raises TraceNotFoundError (404) if the plan never started one."""
    return SuccessResponse.ok(data=observability_service.get_trace_for_plan(plan_id), message="Trace fetched.")


@router.get("/metrics/agents", response_model=SuccessResponse[list[AgentMetrics]], summary="Per-agent metrics")
async def get_agent_metrics(
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> SuccessResponse[list[AgentMetrics]]:
    """Call count, failure count, and latency for every agent, across every trace."""
    return SuccessResponse.ok(data=metrics_service.agent_metrics(), message="Agent metrics fetched.")


@router.get("/metrics/tools", response_model=SuccessResponse[list[ToolMetrics]], summary="Per-tool metrics")
async def get_tool_metrics(
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> SuccessResponse[list[ToolMetrics]]:
    """Call count, failure count, and latency for every tool, across every trace."""
    return SuccessResponse.ok(data=metrics_service.tool_metrics(), message="Tool metrics fetched.")


@router.get("/metrics/ai", response_model=SuccessResponse[AIMetrics], summary="AI call metrics")
async def get_ai_metrics(
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> SuccessResponse[AIMetrics]:
    """Call count, token usage, cost, and latency for AI provider calls, across every trace."""
    return SuccessResponse.ok(data=metrics_service.ai_metrics(), message="AI metrics fetched.")


@router.get(
    "/metrics/summary", response_model=SuccessResponse[ExecutionMetricsSummary], summary="Overall execution metrics"
)
async def get_metrics_summary(
    metrics_service: MetricsService = Depends(get_metrics_service),
) -> SuccessResponse[ExecutionMetricsSummary]:
    """Plan/approval-level aggregates (total execution time, approval latency, counts), plus the breakdowns above."""
    return SuccessResponse.ok(data=metrics_service.summary(), message="Metrics summary fetched.")


@router.get("/traces/{trace_id}", response_model=SuccessResponse[ExecutionTrace], summary="Get one execution trace")
async def get_trace(
    trace_id: str, observability_service: ObservabilityService = Depends(get_observability_service)
) -> SuccessResponse[ExecutionTrace]:
    """Fetch a single trace. Raises TraceNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=observability_service.get_trace(trace_id), message="Trace fetched.")


@router.get(
    "/traces/{trace_id}/timeline",
    response_model=SuccessResponse[list[TimelineEntry]],
    summary="Get a trace's execution timeline",
)
async def get_trace_timeline(
    trace_id: str, observability_service: ObservabilityService = Depends(get_observability_service)
) -> SuccessResponse[list[TimelineEntry]]:
    """Every agent/tool/AI-call/approval event in a trace, oldest first."""
    trace = observability_service.get_trace(trace_id)
    return SuccessResponse.ok(data=build_timeline(trace), message="Timeline fetched.")


@router.get(
    "/traces/{trace_id}/export", response_model=SuccessResponse[str], summary="Export a trace as JSON, Markdown, or CSV"
)
async def export_trace(
    trace_id: str,
    format: Literal["json", "markdown", "csv"] = "json",
    observability_service: ObservabilityService = Depends(get_observability_service),
    trace_exporter: TraceExporter = Depends(get_trace_exporter),
) -> SuccessResponse[str]:
    """Export a trace as a JSON, Markdown, or CSV string."""
    trace = observability_service.get_trace(trace_id)
    content = trace_exporter.export(trace, _EXPORT_FORMATS[format])
    return SuccessResponse.ok(data=content, message=f"Trace exported as {format}.")
