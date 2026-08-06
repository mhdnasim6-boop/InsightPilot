"""export_cluster_mermaid: a Mermaid graph of the worker fleet and its active assignments.

A new, small generator — not a reuse of ``generate_execution_mermaid()``/
``generate_plan_mermaid()`` (Planning/Execution Architecture), which
render one plan's own step DAG; this renders a completely different
graph shape (workers as nodes, assignments as edges to step ids), so
there is no existing generator to reuse here, unlike ``workflows/exporters/mermaid_exporter.py``.
"""

from backend.distributed.models.task_assignment import TaskAssignment
from backend.distributed.models.worker import Worker

_STATUS_LABEL = {
    "online": "🟢", "busy": "🟡", "offline": "⚫", "failed": "🔴", "draining": "🟠",
}


def export_cluster_mermaid(workers: list[Worker], assignments: list[TaskAssignment]) -> str:
    """Render the worker fleet and its currently active assignments as a Mermaid flowchart."""
    lines = ["flowchart LR"]
    for worker in workers:
        icon = _STATUS_LABEL.get(worker.status.value, "")
        capacity = f"{len(worker.active_tasks)}/{worker.maximum_parallel_tasks}"
        lines.append(f'    {worker.worker_id}["{icon} {worker.hostname}<br/>{capacity}"]')

    for assignment in assignments:
        lines.append(f'    {assignment.worker_id} -->|{assignment.node_name}| {assignment.step_id}["{assignment.step_id}"]')

    return "\n".join(lines)
