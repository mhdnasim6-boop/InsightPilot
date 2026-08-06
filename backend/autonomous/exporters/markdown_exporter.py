"""export_optimization_report_markdown: human-readable Markdown export of an OptimizationReport."""

from backend.autonomous.models.optimization_report import OptimizationReport

_SEVERITY_ICON = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}


def export_optimization_report_markdown(report: OptimizationReport) -> str:
    """Render a complete OptimizationReport as Markdown."""
    lines = [
        f"# Optimization Report `{report.report_id}`",
        "",
        f"Generated: {report.generated_at.isoformat()}",
        "",
        report.summary or "_No summary._",
        "",
        "## Decisions",
        "",
        "| Analyzer | Verdict | Bottlenecks | Notes |",
        "|---|---|---|---|",
    ]
    for decision in report.decisions:
        lines.append(
            f"| {decision.analyzer_name} | {decision.verdict.value} | "
            f"{len(decision.bottleneck_ids)} | {decision.notes or '—'} |"
        )

    lines.extend(["", "## Bottlenecks", "", "| Severity | Category | Title | Metric | Value | Threshold | Source |", "|---|---|---|---|---|---|---|"])
    for bottleneck in report.bottlenecks:
        icon = _SEVERITY_ICON.get(bottleneck.severity.value, "")
        lines.append(
            f"| {icon} {bottleneck.severity.value} | {bottleneck.category.value} | {bottleneck.title} | "
            f"{bottleneck.metric_name} | {bottleneck.metric_value:g} | {bottleneck.threshold:g} | {bottleneck.source} |"
        )

    lines.extend(["", "## Suggested Actions", "", "| Impact | Category | Title | Description |", "|---|---|---|---|"])
    for action in report.actions:
        lines.append(f"| {action.estimated_impact} | {action.category.value} | {action.title} | {action.description} |")

    lines.extend(["", "## Healing Recommendations (advisory only)", "", "| Risk | Strategy | Title | Rationale |", "|---|---|---|---|"])
    for recommendation in report.recommendations:
        lines.append(
            f"| {recommendation.risk_level} | {recommendation.strategy_name} | "
            f"{recommendation.title} | {recommendation.rationale} |"
        )

    return "\n".join(lines)
