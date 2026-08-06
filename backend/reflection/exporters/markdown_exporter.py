"""Markdown export for one ReflectionResult: a human-readable execution review."""

from backend.reflection.models.reflection_result import ReflectionResult


class MarkdownReflectionExporter:
    """Renders one ReflectionResult as a single Markdown document."""

    def export(self, result: ReflectionResult) -> str:
        """Return ``result`` rendered as Markdown."""
        review = result.review
        lines = [
            f"# Execution Review — {result.plan_id}",
            "",
            f"**Generated:** {result.generated_at.isoformat()}  ",
            f"**Overall success:** {'Yes' if review.overall_success else 'No'}  ",
            f"**Execution score:** {review.execution_score.value:.0f}/100 ({review.execution_score.label})  ",
            f"**Efficiency score:** {review.efficiency_score.value:.0f}/100 ({review.efficiency_score.label})  ",
            f"**Confidence score:** {review.confidence_score.value:.0f}/100 ({review.confidence_score.label})  ",
            "",
            "## Strengths",
            *self._bullets([s for s in review.strengths]),
            "",
            "## Weaknesses",
            *self._bullets([w for w in review.weaknesses]),
            "",
            "## Recommendations",
            *self._bullets([f"**[{r.priority.value}]** {r.message} — _{r.reason}_" for r in review.recommendations]),
            "",
            "## Future Improvements",
            *self._bullets([f"**{i.area}:** {i.description} ({i.expected_impact})" for i in review.future_improvements]),
            "",
        ]
        return "\n".join(lines)

    def _bullets(self, items: list[str]) -> list[str]:
        if not items:
            return ["*(none)*"]
        return [f"- {item}" for item in items]
