"""Request body for POST /api/v1/visualizations."""

from pydantic import BaseModel

from backend.analysis.models.result import AnalysisResult
from backend.ingestion.models.dataset import BusinessDataset
from backend.visualization.models.layout import LayoutType


class VisualizationRequest(BaseModel):
    """Everything needed to generate and render a VisualizationResult over HTTP."""

    analysis_result: AnalysisResult
    dataset: BusinessDataset | None = None
    layout_type: LayoutType = LayoutType.DETAILED_ANALYSIS
    theme: str = "light"
