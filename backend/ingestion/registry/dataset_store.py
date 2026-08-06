"""In-memory dataset_id -> BusinessDataset store.

Mirrors ``DataFrameStore`` exactly, but stores the metadata object rather
than the DataFrame itself. Added in the dashboard phase so datasets that
have been ingested (or cleaned) can be listed for a dataset selector —
``IngestionService.ingest()``/``CleaningService.clean()`` return a
``BusinessDataset`` to their caller but never persisted a registry of
"every dataset ingested so far" themselves.
"""

from backend.ingestion.models.dataset import BusinessDataset


class BusinessDatasetStore:
    """Process-wide store of ingested/cleaned datasets, keyed by dataset ID."""

    def __init__(self) -> None:
        self._datasets: dict[str, BusinessDataset] = {}

    def put(self, dataset: BusinessDataset) -> None:
        """Store (or overwrite) a dataset, keyed by its own ``dataset_id``."""
        self._datasets[dataset.dataset_id] = dataset

    def get(self, dataset_id: str) -> BusinessDataset | None:
        """Return the dataset for a dataset ID, or None if not present."""
        return self._datasets.get(dataset_id)

    def list(self) -> list[BusinessDataset]:
        """Return every stored dataset, most recently added first."""
        return list(reversed(self._datasets.values()))

    def delete(self, dataset_id: str) -> bool:
        """Remove a stored dataset. Returns True if it existed."""
        return self._datasets.pop(dataset_id, None) is not None
