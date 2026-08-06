"""generate_execution_mermaid(): the plan's existing Mermaid flowchart, with each
step highlighted by its current NodeStatus.

Reuses ``backend.planning.visualization.mermaid.generate_plan_mermaid()``
as-is for the base flowchart (nodes + dependency edges) — this module
only appends Mermaid ``classDef``/``class`` styling directives on top,
never touching that generator.
"""

from backend.execution.state.execution_state import ExecutionState
from backend.execution.state.node_status import NodeStatus
from backend.planning.models.plan import ExecutionPlan
from backend.planning.visualization.mermaid import generate_plan_mermaid

_CLASS_NAME: dict[NodeStatus, str] = {
    NodeStatus.PENDING: "waiting",
    NodeStatus.QUEUED: "waiting",
    NodeStatus.RUNNING: "running",
    NodeStatus.COMPLETED: "completed",
    NodeStatus.FAILED: "failed",
    NodeStatus.PAUSED: "paused",
    NodeStatus.CANCELLED: "cancelled",
    NodeStatus.SKIPPED: "waiting",
}

_CLASS_DEFS: dict[str, str] = {
    "waiting": "classDef waiting fill:#e5e7eb,stroke:#6b7280,color:#111827;",
    "running": "classDef running fill:#fef08a,stroke:#ca8a04,color:#111827;",
    "completed": "classDef completed fill:#bbf7d0,stroke:#16a34a,color:#111827;",
    "failed": "classDef failed fill:#fecaca,stroke:#dc2626,color:#111827;",
    "paused": "classDef paused fill:#fed7aa,stroke:#ea580c,color:#111827;",
    "cancelled": "classDef cancelled fill:#e5e7eb,stroke:#9ca3af,color:#111827;",
}


def generate_execution_mermaid(plan: ExecutionPlan, state: ExecutionState | None = None) -> str:
    """Render ``plan`` as Mermaid; highlight each step by ``state``'s current NodeStatus, if given."""
    base = generate_plan_mermaid(plan)
    if state is None or not state.steps:
        return base

    used_classes = sorted({_CLASS_NAME[node.status] for node in state.steps.values()})
    lines = [base, ""]
    lines.extend(_CLASS_DEFS[class_name] for class_name in used_classes)
    lines.extend(f"class {step_id} {_CLASS_NAME[node.status]};" for step_id, node in state.steps.items())
    return "\n".join(lines)
