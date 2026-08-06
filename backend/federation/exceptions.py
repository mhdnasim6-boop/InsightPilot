"""Federation layer exception hierarchy.

All inherit from ``InsightPilotError``, so the existing global exception
handlers convert them into the unified API response envelope with no
special-casing — mirrors every other phase's own exception module.
"""

from backend.core.exceptions import InsightPilotError


class FederationError(InsightPilotError):
    """Base class for every federation-layer exception."""

    status_code = 500
    error_type = "FederationError"


class ClusterNotFoundError(FederationError):
    """Raised when a cluster is looked up by an unregistered cluster_id."""

    status_code = 404
    error_type = "ClusterNotFoundError"


class InvalidClusterStateError(FederationError):
    """Raised when a requested transition doesn't make sense for a cluster's current status."""

    status_code = 422
    error_type = "InvalidClusterStateError"


class NoEligibleClusterError(FederationError):
    """Raised when a routing request has no cluster capable of serving it."""

    status_code = 422
    error_type = "NoEligibleClusterError"


class RoutingDecisionNotFoundError(FederationError):
    """Raised when a routing decision is looked up by an unknown decision_id."""

    status_code = 404
    error_type = "RoutingDecisionNotFoundError"


class CannotRemoveLocalClusterError(FederationError):
    """Raised when a caller tries to remove this process's own local cluster entry."""

    status_code = 422
    error_type = "CannotRemoveLocalClusterError"
