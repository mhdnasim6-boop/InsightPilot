"""AnalyzeDatasetTool: wraps AnalysisService.analyze() — nothing else."""

from backend.analysis.models.result import AnalysisResult
from backend.services.analysis_service import AnalysisService
from backend.tools.base.tool import Tool
from backend.tools.models.inputs import AnalyzeDatasetInput


class AnalyzeDatasetTool(Tool[AnalyzeDatasetInput, AnalysisResult]):
    """Runs every analyzer against a CleaningOutcome's cleaned dataset."""

    name = "analyze_dataset"
    description = "Run statistics/KPI/trend/correlation/anomaly/insight analysis against a cleaned dataset."
    input_model = AnalyzeDatasetInput
    output_model = AnalysisResult

    def __init__(self, analysis_service: AnalysisService) -> None:
        self._analysis_service = analysis_service

    async def execute(self, tool_input: AnalyzeDatasetInput) -> AnalysisResult:
        return self._analysis_service.analyze(tool_input.cleaning_outcome)
