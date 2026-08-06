"""export_federation_json: JSON export of the whole cluster fleet + routing decisions."""

import json

from backend.federation.models.cluster import Cluster
from backend.federation.models.federation_statistics import FederationStatistics
from backend.federation.models.routing_decision import RoutingDecision


def export_federation_json(
    clusters: list[Cluster], routing_decisions: list[RoutingDecision], statistics: FederationStatistics
) -> str:
    """Serialize every cluster, every routing decision, and federation statistics as one JSON document."""
    payload = {
        "statistics": statistics.model_dump(mode="json"),
        "clusters": [cluster.model_dump(mode="json") for cluster in clusters],
        "routing_decisions": [decision.model_dump(mode="json") for decision in routing_decisions],
    }
    return json.dumps(payload, indent=2)
