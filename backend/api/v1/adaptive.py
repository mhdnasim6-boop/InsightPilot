"""Adaptive planning endpoints: optimize (and remember) a plan, preview what
optimizing it would suggest without remembering, and inspect/export past
optimizations.

Thin HTTP wrappers only — every endpoint here is a direct call into
``AdaptivePlanningService``, never a parallel implementation. Route
order: ``/adaptive/statistics``/``/adaptive/history`` are literal
segments with no ``/adaptive/{id}`` route to collide with (this phase
has no bare get-by-id endpoint — see ``AdaptivePlanningService``'s own
docstring), and ``/adaptive/export/{format}/{id}`` is a distinct,
3-segment shape, so no ordering ambiguity exists here at all.
"""

from typing import Literal

from fastapi import APIRouter, Depends

from backend.adaptive.models.optimization_result import OptimizationResult
from backend.adaptive.models.optimization_statistics import OptimizationStatistics
from backend.adaptive.services.adaptive_planning_service import AdaptivePlanningService
from backend.dependencies.adaptive import get_adaptive_planning_service
from backend.schemas.adaptive_request import AdaptiveOptimizeRequest
from backend.schemas.response import SuccessResponse

router = APIRouter(prefix="/adaptive")


@router.get("/statistics", response_model=SuccessResponse[OptimizationStatistics], summary="Get adaptive planning statistics")
async def get_adaptive_statistics(
    adaptive_service: AdaptivePlanningService = Depends(get_adaptive_planning_service),
) -> SuccessResponse[OptimizationStatistics]:
    """Aggregate counts/averages across every stored optimization."""
    return SuccessResponse.ok(data=adaptive_service.statistics(), message="Statistics fetched.")


@router.get("/history", response_model=SuccessResponse[list[OptimizationResult]], summary="List every optimization")
async def get_adaptive_history(
    adaptive_service: AdaptivePlanningService = Depends(get_adaptive_planning_service),
) -> SuccessResponse[list[OptimizationResult]]:
    """Return every stored optimization, most recently generated first."""
    return SuccessResponse.ok(data=adaptive_service.history(), message="History fetched.")


@router.get(
    "/export/{export_format}/{optimization_id}", response_model=SuccessResponse[str], summary="Export one optimization"
)
async def export_optimization(
    export_format: Literal["json", "markdown"],
    optimization_id: str,
    adaptive_service: AdaptivePlanningService = Depends(get_adaptive_planning_service),
) -> SuccessResponse[str]:
    """Export one optimization as JSON or Markdown. Raises OptimizationNotFoundError (404) if unknown."""
    return SuccessResponse.ok(
        data=adaptive_service.export(optimization_id, export_format), message=f"Optimization exported as {export_format}."
    )


@router.post("/optimize", response_model=SuccessResponse[OptimizationResult], summary="Optimize a plan")
async def optimize_plan(
    request: AdaptiveOptimizeRequest,
    adaptive_service: AdaptivePlanningService = Depends(get_adaptive_planning_service),
) -> SuccessResponse[OptimizationResult]:
    """Optimize ``request.plan`` against historical evidence and remember the result."""
    result = adaptive_service.optimize(request.plan, request.session_id)
    return SuccessResponse.ok(data=result, message=f"Optimization '{result.optimization_id}' generated.")


@router.post("/explain", response_model=SuccessResponse[OptimizationResult], summary="Preview optimizing a plan")
async def explain_plan(
    request: AdaptiveOptimizeRequest,
    adaptive_service: AdaptivePlanningService = Depends(get_adaptive_planning_service),
) -> SuccessResponse[OptimizationResult]:
    """Preview what optimizing ``request.plan`` would suggest — no memory write, no side effects."""
    result = adaptive_service.explain(request.plan, request.session_id)
    return SuccessResponse.ok(data=result, message="Optimization preview generated.")
