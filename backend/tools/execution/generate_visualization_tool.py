"""GenerateVisualizationTool: wraps VisualizationService.generate() — nothing else."""

from backend.services.visualization_service import VisualizationService
from backend.tools.base.tool import Tool
from backend.tools.models.inputs import GenerateVisualizationInput
from backend.visualization.models.result import VisualizationResult


class GenerateVisualizationTool(Tool[GenerateVisualizationInput, VisualizationResult]):
    """Recommends and renders charts plus a layout for an AnalysisResult."""

    name = "generate_visualization"
    description = "Recommend and render charts plus a layout for an AnalysisResult."
    input_model = GenerateVisualizationInput
    output_model = VisualizationResult

    def __init__(self, visualization_service: VisualizationService) -> None:
        self._visualization_service = visualization_service

    async def execute(self, tool_input: GenerateVisualizationInput) -> VisualizationResult:
        return self._visualization_service.generate(tool_input.analysis_result, dataset=tool_input.dataset)
