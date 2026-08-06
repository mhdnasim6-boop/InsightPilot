"""export_workflow_markdown: human-readable Markdown export of a Workflow
(+ its latest execution)."""

from backend.workflows.models.workflow import Workflow
from backend.workflows.models.workflow_execution import WorkflowExecution


def export_workflow_markdown(workflow: Workflow, latest_execution: WorkflowExecution | None) -> str:
    """Render a workflow (and its most recent execution, if any) as Markdown."""
    lines = [
        f"# Workflow: {workflow.definition.name}",
        "",
        workflow.definition.description or "_No description._",
        "",
        f"- **Workflow ID:** `{workflow.workflow_id}`",
        f"- **Status:** {workflow.status.value}",
        f"- **Version:** {workflow.version}",
        f"- **Tags:** {', '.join(workflow.definition.tags) or '—'}",
        "",
        "## Steps",
        "",
        "| Step | Name | Agent | Depends On |",
        "|---|---|---|---|",
    ]
    for step in workflow.definition.steps:
        lines.append(f"| {step.step_id} | {step.name} | {step.node_name} | {', '.join(step.dependencies) or '—'} |")

    if latest_execution is not None:
        lines.extend([
            "",
            "## Latest Execution",
            "",
            f"- **Execution ID:** `{latest_execution.workflow_execution_id}`",
            f"- **Status:** {latest_execution.status.value}",
            f"- **Completed steps:** {len(latest_execution.completed_steps)}",
            f"- **Pending steps:** {len(latest_execution.pending_steps)}",
            f"- **Failed steps:** {len(latest_execution.failed_steps)}",
            f"- **Trace ID:** `{latest_execution.trace_id or '—'}`",
            f"- **Optimization ID:** `{latest_execution.optimization_id or '—'}`",
            f"- **Reflection ID:** `{latest_execution.reflection_id or '—'}`",
        ])

    return "\n".join(lines)
