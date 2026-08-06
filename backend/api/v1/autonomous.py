"""Autonomous optimization endpoints: trigger an analysis pass, list/inspect past
reports, aggregate statistics, and every advisory recommendation ever generated —
thin wrappers over ``AutonomousService``, exactly like every other router in this
codebase.
"""

from fastapi import APIRouter, Depends

from backend.autonomous.models.healing_recommendation import HealingRecommendation
from backend.autonomous.models.optimization_report import OptimizationReport
from backend.autonomous.models.optimization_statistics import OptimizationStatistics
from backend.autonomous.services.autonomous_service import AutonomousService
from backend.dependencies.autonomous import get_autonomous_service
from backend.schemas.response import SuccessResponse
from backend.security.authorization.permission import Permission
from backend.security.middleware.authorization import require_permission
from backend.security.models.authenticated_user import AuthenticatedUser

router = APIRouter(prefix="/autonomous")


@router.post("/analyze", response_model=SuccessResponse[OptimizationReport], summary="Run one analysis pass")
async def analyze(
    service: AutonomousService = Depends(get_autonomous_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.RUN_ANALYSIS)),
) -> SuccessResponse[OptimizationReport]:
    """Analyze the platform's own current statistics and produce a new OptimizationReport.

    Read-only against every reused service — nothing here modifies any
    execution, workflow, distributed, federation, security, memory,
    reflection, or plugin state. Every recommendation the resulting
    report contains is advisory only.
    """
    report = service.analyze()
    return SuccessResponse.ok(data=report, message=f"Optimization report '{report.report_id}' generated.")


@router.get("/reports", response_model=SuccessResponse[list[OptimizationReport]], summary="List every optimization report")
async def list_reports(
    service: AutonomousService = Depends(get_autonomous_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[list[OptimizationReport]]:
    """Every report generated so far, in generation order."""
    return SuccessResponse.ok(data=service.list_reports(), message="Optimization reports fetched.")


@router.get("/reports/{report_id}", response_model=SuccessResponse[OptimizationReport], summary="Get one optimization report")
async def get_report(
    report_id: str,
    service: AutonomousService = Depends(get_autonomous_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[OptimizationReport]:
    """Fetch one report by id. Raises OptimizationReportNotFoundError (404) if unknown."""
    return SuccessResponse.ok(data=service.get_report(report_id), message="Optimization report fetched.")


@router.get("/statistics", response_model=SuccessResponse[OptimizationStatistics], summary="Autonomous optimization statistics")
async def get_statistics(
    service: AutonomousService = Depends(get_autonomous_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[OptimizationStatistics]:
    """Aggregate counts across every report generated so far."""
    return SuccessResponse.ok(data=service.statistics(), message="Autonomous optimization statistics fetched.")


@router.get(
    "/recommendations", response_model=SuccessResponse[list[HealingRecommendation]], summary="List every healing recommendation"
)
async def list_recommendations(
    service: AutonomousService = Depends(get_autonomous_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[list[HealingRecommendation]]:
    """Every advisory healing recommendation across every report ever generated."""
    return SuccessResponse.ok(data=service.list_recommendations(), message="Healing recommendations fetched.")
