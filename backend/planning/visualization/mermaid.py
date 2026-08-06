"""Mermaid flowchart export for an ExecutionPlan's steps and dependencies."""

from backend.planning.models.plan import ExecutionPlan


def generate_plan_mermaid(plan: ExecutionPlan) -> str:
    """Render a plan's steps as Mermaid flowchart nodes, edges from dependencies."""
    lines = ["graph TD;"]
    for step in plan.steps:
        label = step.name.replace('"', "'")
        lines.append(f'    {step.step_id}["{label}"]')
    for step in plan.steps:
        for dependency in step.dependencies:
            lines.append(f"    {dependency} --> {step.step_id}")
    return "\n".join(lines)
