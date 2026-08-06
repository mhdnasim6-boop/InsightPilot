"""Markdown export for one OptimizationResult: a human-readable before/after
optimization report.
"""

from backend.adaptive.models.optimization_result import OptimizationResult


class MarkdownOptimizationExporter:
    """Renders one OptimizationResult as a single Markdown document."""

    def export(self, result: OptimizationResult) -> str:
        """Return ``result`` rendered as Markdown."""
        lines = [
            f"# Plan Optimization — {result.plan_id}",
            "",
            f"**Generated:** {result.generated_at.isoformat()}  ",
            f"**Original steps:** {len(result.original_plan.steps)}  ",
            f"**Optimized steps:** {len(result.optimized_plan.steps)}  ",
            f"**Estimated execution savings:** {result.execution_savings_estimate_seconds:.1f}s  ",
            f"**Estimated approval savings:** {result.approval_savings_estimate}  ",
            f"**Parallelism improved:** {'Yes' if result.parallelism_improved else 'No'}  ",
            "",
            "## Decisions",
            *self._bullets(
                [
                    f"{'**[applied]** ' if d.applied else ''}**[{d.category.value}]** {d.message} — _{d.reason}_"
                    for d in result.decisions
                ]
            ),
            "",
        ]
        return "\n".join(lines)

    def _bullets(self, items: list[str]) -> list[str]:
        if not items:
            return ["*(none)*"]
        return [f"- {item}" for item in items]
