"""Runs every registered chart generator and collects what fires (and what doesn't, and why)."""

from collections.abc import Sequence

from backend.visualization.charts.base import ChartGenerator
from backend.visualization.models.context import ChartContext
from backend.visualization.models.recommendation import (
    RecommendationResult,
    SkippedChart,
)


class ChartRecommendationEngine:
    """Deterministically decides which charts to generate for a given context.

    Each generator's own ``applicable()`` check *is* the recommendation
    rule (e.g. "trend data exists" -> line chart, "correlation matrix
    exists" -> correlation matrix chart) — this engine only orchestrates
    calling every registered generator and collecting the outcome.
    """

    def __init__(self, generators: Sequence[ChartGenerator]) -> None:
        self._generators = generators

    def recommend(self, context: ChartContext) -> RecommendationResult:
        """Run every registered generator, returning generated charts in priority order."""
        charts = []
        skipped = []
        for generator in self._generators:
            is_applicable, reason = generator.applicable(context)
            if not is_applicable:
                skipped.append(SkippedChart(chart_type=generator.chart_type, reason=reason or "Not applicable."))
                continue
            charts.append(generator.generate(context))

        charts.sort(key=lambda spec: -spec.priority)
        return RecommendationResult(charts=charts, skipped=skipped)
