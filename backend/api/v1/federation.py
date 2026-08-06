"""Federation endpoints: cluster registration/removal, health, statistics, and
routing decisions — thin wrappers over ``FederationService``, exactly like
every other router in this codebase.
"""

from fastapi import APIRouter, Depends

from backend.dependencies.federation import get_federation_service
from backend.federation.models.cluster import Cluster
from backend.federation.models.federation_statistics import FederationStatistics
from backend.federation.models.routing_decision import RoutingDecision
from backend.federation.services.federation_service import FederationService
from backend.schemas.federation_request import (
    RegisterClusterRequest,
    RemoveClusterRequest,
)
from backend.schemas.response import SuccessResponse
from backend.security.authorization.permission import Permission
from backend.security.middleware.authorization import require_permission
from backend.security.models.authenticated_user import AuthenticatedUser

router = APIRouter(prefix="/federation")


@router.get("/clusters", response_model=SuccessResponse[list[Cluster]], summary="List every registered cluster")
async def list_clusters(
    service: FederationService = Depends(get_federation_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[list[Cluster]]:
    """Every registered cluster (including the local one), after a health sweep."""
    return SuccessResponse.ok(data=service.list_clusters(), message="Clusters fetched.")


@router.post("/clusters/register", response_model=SuccessResponse[Cluster], summary="Register a cluster")
async def register_cluster(
    body: RegisterClusterRequest,
    service: FederationService = Depends(get_federation_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_SYSTEM)),
) -> SuccessResponse[Cluster]:
    """Register (or re-register) a remote cluster. Idempotent by cluster_id."""
    cluster = service.register_cluster(
        body.cluster_id, body.name, body.endpoint, body.capabilities, body.version, body.registered_workers, body.metadata,
    )
    return SuccessResponse.ok(data=cluster, message=f"Cluster '{cluster.cluster_id}' registered.")


@router.post("/clusters/remove", response_model=SuccessResponse[bool], summary="Remove a cluster")
async def remove_cluster(
    body: RemoveClusterRequest,
    service: FederationService = Depends(get_federation_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.MANAGE_SYSTEM)),
) -> SuccessResponse[bool]:
    """Deregister a remote cluster. Raises 404 if unknown, 422 for the local cluster."""
    service.remove_cluster(body.cluster_id)
    return SuccessResponse.ok(data=True, message=f"Cluster '{body.cluster_id}' removed.")


@router.get("/health", response_model=SuccessResponse[list[Cluster]], summary="Cluster health snapshot")
async def get_health(
    service: FederationService = Depends(get_federation_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[list[Cluster]]:
    """Every cluster's current health snapshot, after a fresh sweep."""
    return SuccessResponse.ok(data=service.get_health(), message="Cluster health fetched.")


@router.get("/statistics", response_model=SuccessResponse[FederationStatistics], summary="Federation statistics")
async def get_statistics(
    service: FederationService = Depends(get_federation_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[FederationStatistics]:
    """Aggregate counts across the whole cluster fleet."""
    return SuccessResponse.ok(data=service.federation_statistics(), message="Federation statistics fetched.")


@router.get("/routing", response_model=SuccessResponse[list[RoutingDecision]], summary="Routing decisions")
async def get_routing_decisions(
    service: FederationService = Depends(get_federation_service),
    _: AuthenticatedUser = Depends(require_permission(Permission.VIEW_DATA)),
) -> SuccessResponse[list[RoutingDecision]]:
    """Every routing decision ever made, in creation order."""
    return SuccessResponse.ok(data=service.list_routing_decisions(), message="Routing decisions fetched.")
