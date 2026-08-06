"""Reflection endpoints: generate a reflection over a completed execution, and
fetch/list/export/aggregate previously generated ones.

Thin HTTP wrappers only — every endpoint here is a direct call into
``ReflectionService``, never a parallel implementation. ``generate_reflection``
is the one handler that does real fetching of its own: it resolves the
``ExecutionTrace``/``CollaborationTask``/``ReportDocument`` referenced by
the request via ``ObservabilityService``/``CollaborationService``/
``ReportService`` before handing them to ``ReflectionService.generate()``
— exactly what those services already exist for. Route order matters:
``/reflection/list``/``/reflection/statistics`` are registered before
``/reflection/{reflection_id}`` so FastAPI matches them as literal path
segments (same reasoning as ``/memory/statistics`` vs. ``/memory/{memory_id}``).
"""

from typing import Literal

from fastapi import APIRouter, Depends

from backend.collaboration.services.collaboration_service import CollaborationService
from backend.dependencies.collaboration import get_collaboration_service
from backend.dependencies.observability import get_observability_service
from backend.dependencies.reflection import get_reflection_service
from backend.dependencies.reporting import get_report_service
from backend.observability.services.observability_service import ObservabilityService
from backend.reflection.models.reflection_result import ReflectionResult
from backend.reflection.models.reflection_statistics import ReflectionStatistics
from backend.reflection.services.reflection_service import ReflectionService
from backend.schemas.reflection_request import ReflectionGenerateRequest
from backend.schemas.response import SuccessResponse
from backend.services.report_service import ReportService

router = APIRouter(prefix="/reflection")


@router.get("/list", response_model=SuccessResponse[list[ReflectionResult]], summary="List every reflection")
async def list_reflections(
    reflection_service: ReflectionService = Depends(get_reflection_service),
) -> SuccessResponse[list[ReflectionResult]]:
    """Return every stored reflection, most recently generated first."""
    return SuccessResponse.ok(data=reflection_service.list_all(), message="Reflections fetched.")


@router.get("/statistics", response_model=SuccessResponse[ReflectionStatistics], summary="Get reflection statistics")
async def get_reflection_statistics(
    reflection_service: ReflectionService = Depends(get_reflection_service),
) -> SuccessResponse[ReflectionStatistics]:
    """Aggregate counts/averages across every stored reflection."""
    return SuccessResponse.ok(data=reflection_service.statistics(), message="Statistics fetched.")


@router.get(
    "/export/{export_format}/{reflection_id}", response_model=SuccessResponse[str], summary="Export one reflection"
)
async def export_reflection(
    export_format: Literal["json", "markdown"],
    reflection_id: str,
    reflection_service: ReflectionService = Depends(get_reflection_service),
) -> SuccessResponse[str]:
    """Export one reflection as JSON or Markdown. Raises ReflectionNotFoundError (404) if unknown."""
    return SuccessResponse.ok(
        data=reflection_service.export(reflection_id, export_format), message=f"Reflection exported as {export_format}."
    )


@router.post("/generate", response_model=SuccessResponse[ReflectionResult], summary="Generate a reflection")
async def generate_reflection(
    request: ReflectionGenerateRequest,
    reflection_service: ReflectionService = Depends(get_reflection_service),
    observability_service: ObservabilityService = Depends(get_observability_service),
    collaboration_service: CollaborationService = Depends(get_collaboration_service),
    report_service: ReportService = Depends(get_report_service),
) -> SuccessResponse[ReflectionResult]:
    """Reflect on a completed plan's execution.

    Raises TraceNotFoundError (404) if the plan never produced a trace,
    CollaborationNotFoundError/ReportNotFoundError (404) if
    ``collaboration_id``/``report_id`` were given but don't exist.
    """
    trace = observability_service.get_trace_for_plan(request.plan.plan_id)
    collaboration_task = (
        collaboration_service.get(request.collaboration_id) if request.collaboration_id is not None else None
    )
    report_document = report_service.get_report(request.report_id) if request.report_id is not None else None

    result = reflection_service.generate(request.plan, trace, collaboration_task, report_document)
    return SuccessResponse.ok(data=result, message=f"Reflection '{result.reflection_id}' generated.")


@router.get("/{reflection_id}", response_model=SuccessResponse[ReflectionResult], summary="Get one reflection")
async def get_reflection(
    reflection_id: str, reflection_service: ReflectionService = Depends(get_reflection_service)
) -> SuccessResponse[ReflectionResult]:
    """Fetch one reflection by id. Raises ReflectionNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=reflection_service.get(reflection_id), message="Reflection fetched.")
