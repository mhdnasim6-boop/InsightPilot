"""export_optimization_report_mermaid: a Mermaid graph of bottlenecks -> actions -> recommendations."""

from backend.autonomous.models.optimization_report import OptimizationReport

_SEVERITY_ICON = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}


def export_optimization_report_mermaid(report: OptimizationReport) -> str:
    """Render a report's own bottleneck -> action -> recommendation chain as a Mermaid flowchart."""
    lines = ["flowchart LR"]

    for bottleneck in report.bottlenecks:
        icon = _SEVERITY_ICON.get(bottleneck.severity.value, "")
        lines.append(f'    {bottleneck.bottleneck_id}["{icon} {bottleneck.title}"]')

    for action in report.actions:
        lines.append(f'    {action.action_id}(["{action.title}"])')
        lines.append(f"    {action.bottleneck_id} --> {action.action_id}")

    for recommendation in report.recommendations:
        lines.append(f'    {recommendation.recommendation_id}{{{{"{recommendation.strategy_name}"}}}}')
        if recommendation.action_id is not None:
            lines.append(f"    {recommendation.action_id} --> {recommendation.recommendation_id}")
        else:
            lines.append(f"    {recommendation.bottleneck_id} --> {recommendation.recommendation_id}")

    return "\n".join(lines)
