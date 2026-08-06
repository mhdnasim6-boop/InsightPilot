"""Results of running the deterministic chart recommendation engine."""

from pydantic import BaseModel, Field

from backend.visualization.models.chart import ChartSpecification, ChartType


class SkippedChart(BaseModel):
    """A chart type the recommendation engine considered but did not generate."""

    chart_type: ChartType
    reason: str


class RecommendationResult(BaseModel):
    """Everything the recommendation engine decided, and why."""

    charts: list[ChartSpecification] = Field(default_factory=list)
    skipped: list[SkippedChart] = Field(default_factory=list)
