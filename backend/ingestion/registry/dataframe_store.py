"""In-memory dataset_id -> DataFrame store.

The concrete mechanism behind ``BusinessDataset.dataframe_reference``:
agents that need the full DataFrame (not just the metadata/sample already
on ``BusinessDataset``) resolve it here — never by re-reading the source
file themselves.
"""

import pandas as pd


class DataFrameStore:
    """Process-wide store of loaded DataFrames, keyed by dataset ID."""

    def __init__(self) -> None:
        self._frames: dict[str, pd.DataFrame] = {}

    def put(self, dataset_id: str, dataframe: pd.DataFrame) -> None:
        """Store a DataFrame under a dataset ID."""
        self._frames[dataset_id] = dataframe

    def get(self, dataset_id: str) -> pd.DataFrame | None:
        """Return the DataFrame for a dataset ID, or None if not present."""
        return self._frames.get(dataset_id)

    def delete(self, dataset_id: str) -> bool:
        """Remove a stored DataFrame. Returns True if it existed."""
        return self._frames.pop(dataset_id, None) is not None
