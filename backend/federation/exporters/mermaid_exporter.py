"""export_federation_mermaid: a Mermaid graph of cluster topology and active routing.

A new, small generator — this renders a completely different graph
shape (clusters as nodes, routing decisions as edges to workflow ids)
from ``backend.distributed.exporters.mermaid_exporter.export_cluster_mermaid``
(workers/assignments), so there is nothing to reuse from that one either.
"""

from backend.federation.models.cluster import Cluster
from backend.federation.models.routing_decision import RoutingDecision

_STATUS_LABEL = {
    "online": "🟢", "degraded": "🟡", "offline": "⚫", "maintenance": "🟠", "failed": "🔴",
}


def export_federation_mermaid(clusters: list[Cluster], routing_decisions: list[RoutingDecision]) -> str:
    """Render the cluster topology and its currently active routing decisions as a Mermaid flowchart."""
    lines = ["flowchart LR"]
    for cluster in clusters:
        icon = _STATUS_LABEL.get(cluster.status.value, "")
        label = "local" if cluster.is_local else cluster.name
        capacity = f"{len(cluster.active_remote_executions)}/{cluster.capabilities.maximum_concurrent_executions}"
        lines.append(f'    {cluster.cluster_id}["{icon} {label}<br/>{capacity}"]')

    for decision in routing_decisions:
        lines.append(
            f'    {decision.selected_cluster_id} -->|{decision.status.value}| {decision.workflow_id}["{decision.workflow_id}"]'
        )

    return "\n".join(lines)
