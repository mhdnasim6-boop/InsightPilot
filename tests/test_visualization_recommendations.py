"""Tests for ChartRecommendationEngine: deterministic applicable/skip collection."""

from backend.analysis.models.anomaly import AnomalyAnalysisResult
from backend.analysis.models.correlation import CorrelationAnalysisResult
from backend.analysis.models.dataset_summary import DatasetSummary
from backend.analysis.models.result import AnalysisResult
from backend.analysis.models.statistics import DescriptiveStatistics
from backend.analysis.models.trend import TrendAnalysisResult
from backend.utils.time import utc_now
from backend.visualization.charts.base import ChartGenerator
from backend.visualization.models.chart import ChartSpecification, ChartType
from backend.visualization.models.context import ChartContext
from backend.visualization.recommendations.engine import ChartRecommendationEngine


class _AlwaysApplicable(ChartGenerator):
    chart_type = ChartType.BAR

    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        return True, None

    def generate(self, context: ChartContext) -> ChartSpecification:
        return ChartSpecification(chart_id="always", title="Always", chart_type=self.chart_type, priority=3)


class _NeverApplicable(ChartGenerator):
    chart_type = ChartType.SCATTER

    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        return False, "Deliberately never applicable."

    def generate(self, context: ChartContext) -> ChartSpecification:
        raise AssertionError("generate() must never be called when applicable() is False")


class _HighPriority(ChartGenerator):
    chart_type = ChartType.LINE

    def applicable(self, context: ChartContext) -> tuple[bool, str | None]:
        return True, None

    def generate(self, context: ChartContext) -> ChartSpecification:
        return ChartSpecification(chart_id="high", title="High", chart_type=self.chart_type, priority=9)


def _empty_context() -> ChartContext:
    now = utc_now()
    analysis_result = AnalysisResult(
        analysis_id="a1",
        dataset_id="d1",
        analysis_timestamp=now,
        dataset_summary=DatasetSummary(row_count=0, column_count=0, missing_values=0, memory_usage_bytes=0, duplicate_count=0),
        descriptive_statistics=DescriptiveStatistics(),
        trends=TrendAnalysisResult(applicable=False),
        anomalies=AnomalyAnalysisResult(applicable=False),
        correlations=CorrelationAnalysisResult(applicable=False),
        execution_time=0.0,
    )
    return ChartContext(analysis_result=analysis_result)


def test_recommend_collects_applicable_charts_and_skips_the_rest() -> None:
    engine = ChartRecommendationEngine([_AlwaysApplicable(), _NeverApplicable()])

    result = engine.recommend(_empty_context())

    assert len(result.charts) == 1
    assert result.charts[0].chart_id == "always"
    assert len(result.skipped) == 1
    assert result.skipped[0].chart_type == ChartType.SCATTER
    assert result.skipped[0].reason == "Deliberately never applicable."


def test_recommend_never_calls_generate_for_a_non_applicable_generator() -> None:
    # _NeverApplicable.generate() raises AssertionError if ever called.
    engine = ChartRecommendationEngine([_NeverApplicable()])
    result = engine.recommend(_empty_context())
    assert result.charts == []


def test_recommend_orders_charts_by_priority_descending() -> None:
    engine = ChartRecommendationEngine([_AlwaysApplicable(), _HighPriority()])

    result = engine.recommend(_empty_context())

    assert [chart.chart_id for chart in result.charts] == ["high", "always"]


def test_recommend_with_no_generators_returns_empty_result() -> None:
    engine = ChartRecommendationEngine([])
    result = engine.recommend(_empty_context())
    assert result.charts == []
    assert result.skipped == []
