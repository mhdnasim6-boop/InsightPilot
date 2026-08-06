"""Loads CSV files with pandas. Loading only — no cleaning, no transformation."""

import pandas as pd

from backend.ingestion.exceptions.errors import DatasetCorruptedError
from backend.ingestion.loaders.base import DataLoader


class CSVLoader(DataLoader):
    """Loads a ``.csv`` file into a DataFrame via ``pandas.read_csv``."""

    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".csv"})

    def load(self, source_location: str) -> pd.DataFrame:
        try:
            return pd.read_csv(source_location)
        except Exception as exc:
            raise DatasetCorruptedError(f"Failed to load CSV '{source_location}': {exc}") from exc
