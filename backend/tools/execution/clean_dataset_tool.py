"""CleanDatasetTool: wraps CleaningService.clean() — nothing else."""

from backend.cleaning.models.outcome import CleaningOutcome
from backend.services.cleaning_service import CleaningService
from backend.tools.base.tool import Tool
from backend.tools.models.inputs import CleanDatasetInput


class CleanDatasetTool(Tool[CleanDatasetInput, CleaningOutcome]):
    """Runs the default cleaning pipeline against a BusinessDataset."""

    name = "clean_dataset"
    description = "Run the default cleaning pipeline against a BusinessDataset."
    input_model = CleanDatasetInput
    output_model = CleaningOutcome

    def __init__(self, cleaning_service: CleaningService) -> None:
        self._cleaning_service = cleaning_service

    async def execute(self, tool_input: CleanDatasetInput) -> CleaningOutcome:
        return self._cleaning_service.clean(tool_input.dataset)
