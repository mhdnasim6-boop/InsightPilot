"""The central, universal output of the visualization framework.

Every future consumer (a report, a dashboard, a chatbot response, an
executive summary) reads a ``VisualizationResult`` — never builds a chart
itself.
"""

from typing import Any

from pydantic import BaseModel, Field

from backend.visualization.models.chart import ChartSpecification
from backend.visualization.models.layout import Layout


class VisualizationResult(BaseModel):
    """The complete, structured output of visualizing one AnalysisResult."""

    visualization_id: str
    analysis_id: str
    charts: list[ChartSpecification] = Field(default_factory=list)
    layout: Layout
    recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    execution_time: float
