"""Visualization endpoint: recommends charts, builds a layout, and renders
each chart to Plotly figure JSON.

Rendering is done here, server-side, by reusing the existing
``PlotlyExporter`` — the frontend never constructs a chart, it only ever
hands the returned figure JSON straight to ``go.Figure()``.
"""

import json

from fastapi import APIRouter, Depends

from backend.dependencies.visualization import (
    get_plotly_exporter,
    get_theme_registry,
    get_visualization_service,
)
from backend.schemas.response import SuccessResponse
from backend.schemas.visualization_request import VisualizationRequest
from backend.schemas.visualization_response import VisualizationResponse
from backend.services.visualization_service import VisualizationService
from backend.visualization.exporters.plotly_exporter import PlotlyExporter
from backend.visualization.themes.registry import ThemeRegistry

router = APIRouter()


@router.post(
    "/visualizations",
    response_model=SuccessResponse[VisualizationResponse],
    summary="Recommend charts, build a layout, and render each chart to Plotly figure JSON",
)
async def generate_visualizations(
    request: VisualizationRequest,
    visualization_service: VisualizationService = Depends(get_visualization_service),
    exporter: PlotlyExporter = Depends(get_plotly_exporter),
    theme_registry: ThemeRegistry = Depends(get_theme_registry),
) -> SuccessResponse[VisualizationResponse]:
    """Generate a VisualizationResult and pre-render every chart with the requested theme.

    Raises ``UnknownThemeError`` (404) for an unrecognized ``theme`` name —
    consistent with every other "unknown X" lookup in this project.
    """
    result = visualization_service.generate(
        request.analysis_result, dataset=request.dataset, layout_type=request.layout_type
    )
    theme = theme_registry.get(request.theme)

    rendered_charts = {
        chart.chart_id: json.loads(exporter.export(chart, theme=theme).to_json()) for chart in result.charts
    }

    response = VisualizationResponse(visualization_result=result, rendered_charts=rendered_charts)
    return SuccessResponse.ok(data=response, message="Visualizations generated.")
