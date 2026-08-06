"""IngestDatasetTool: wraps IngestionService.ingest() — nothing else."""

from backend.ingestion.models.dataset import BusinessDataset
from backend.services.ingestion_service import IngestionService
from backend.tools.base.tool import Tool
from backend.tools.models.inputs import IngestDatasetInput


class IngestDatasetTool(Tool[IngestDatasetInput, BusinessDataset]):
    """Ingests a file/source reference into a BusinessDataset."""

    name = "ingest_dataset"
    description = "Ingest a file or source reference into a BusinessDataset."
    input_model = IngestDatasetInput
    output_model = BusinessDataset

    def __init__(self, ingestion_service: IngestionService) -> None:
        self._ingestion_service = ingestion_service

    async def execute(self, tool_input: IngestDatasetInput) -> BusinessDataset:
        return self._ingestion_service.ingest(tool_input.dataset_reference)
