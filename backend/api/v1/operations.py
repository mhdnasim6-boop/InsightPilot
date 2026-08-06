"""Operations endpoints: liveness, readiness, diagnostics, configuration,
feature flags — thin wrappers over backend.operations, exactly like every
other router in this codebase.
"""

from fastapi import APIRouter, Depends

from backend.dependencies.operations import (
    get_configuration_validator,
    get_diagnostics_service,
    get_feature_flag_service,
    get_liveness_service,
    get_readiness_service,
)
from backend.dependencies.orchestration import get_graph_builder
from backend.operations.configuration.configuration_validator import (
    ConfigurationValidator,
)
from backend.operations.diagnostics.environment_report import (
    EnvironmentReport,
    build_environment_report,
)
from backend.operations.feature_flags.feature_flag import FeatureFlag
from backend.operations.feature_flags.feature_flag_service import FeatureFlagService
from backend.operations.health.diagnostics import DiagnosticsReport, DiagnosticsService
from backend.operations.health.liveness import LivenessService, LivenessStatus
from backend.operations.health.readiness import ReadinessService, ReadinessStatus
from backend.orchestration.graph.builder import GraphBuilder
from backend.schemas.response import SuccessResponse
from config.settings import Settings, get_settings

router = APIRouter(prefix="/operations")


@router.get("/health", response_model=SuccessResponse[LivenessStatus], summary="Operations liveness probe")
async def get_liveness(service: LivenessService = Depends(get_liveness_service)) -> SuccessResponse[LivenessStatus]:
    """Is this process alive. Always ``alive: true`` if this call returns at all."""
    return SuccessResponse.ok(data=service.check(), message="Service is alive.")


@router.get("/readiness", response_model=SuccessResponse[ReadinessStatus], summary="Operations readiness probe")
async def get_readiness(service: ReadinessService = Depends(get_readiness_service)) -> SuccessResponse[ReadinessStatus]:
    """Is this process ready to serve real traffic — reflects StartupManager's own last recorded run."""
    status = service.check()
    message = "Service is ready." if status.ready else "Service is not ready."
    return SuccessResponse.ok(data=status, message=message)


@router.get("/diagnostics", response_model=SuccessResponse[DiagnosticsReport], summary="Full operational diagnostics")
async def get_diagnostics(
    service: DiagnosticsService = Depends(get_diagnostics_service),
    graph_builder: GraphBuilder = Depends(get_graph_builder),
) -> SuccessResponse[DiagnosticsReport]:
    """Environment, loaded plugins, registered tools/agents, memory usage, profile, and feature flags."""
    report = service.build(graph_metadata=graph_builder.export())
    return SuccessResponse.ok(data=report, message="Diagnostics generated.")


@router.get(
    "/configuration", response_model=SuccessResponse[EnvironmentReport], summary="Resolved configuration + validation"
)
async def get_configuration(
    settings: Settings = Depends(get_settings),
    validator: ConfigurationValidator = Depends(get_configuration_validator),
) -> SuccessResponse[EnvironmentReport]:
    """The active profile, key resolved settings, and the full environment validation result."""
    result = validator.validate(settings)
    report = build_environment_report(settings, result)
    message = "Configuration is valid." if result.is_valid else "Configuration has validation errors."
    return SuccessResponse.ok(data=report, message=message)


@router.get("/feature-flags", response_model=SuccessResponse[list[FeatureFlag]], summary="Every feature flag")
async def get_feature_flags(
    service: FeatureFlagService = Depends(get_feature_flag_service),
) -> SuccessResponse[list[FeatureFlag]]:
    """Every feature flag's current, read-only state."""
    return SuccessResponse.ok(data=service.list_flags(), message="Feature flags fetched.")
