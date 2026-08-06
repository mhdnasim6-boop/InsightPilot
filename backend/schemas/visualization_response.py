"""Response body for POST /api/v1/visualizations.

Bundles the plain, Plotly-independent ``VisualizationResult`` alongside
each chart already rendered to Plotly figure JSON (via the existing
``PlotlyExporter``) — so the frontend only ever needs to hand the figure
JSON to ``go.Figure()`` and render it. No chart-construction logic lives
in the frontend; ``PlotlyExporter`` (backend, already built and tested in
the visualization phase) is reused as-is.
"""

from typing import Any

from pydantic import BaseModel, Field

from backend.visualization.models.result import VisualizationResult


class VisualizationResponse(BaseModel):
    """A VisualizationResult plus pre-rendered Plotly figure JSON per chart."""

    visualization_result: VisualizationResult
    rendered_charts: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="chart_id -> Plotly figure JSON (from Figure.to_json())."
    )
