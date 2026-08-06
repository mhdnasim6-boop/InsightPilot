"""Loads Excel files with pandas. Loading only — no cleaning, no transformation."""

import pandas as pd

from backend.ingestion.exceptions.errors import DatasetCorruptedError
from backend.ingestion.loaders.base import DataLoader


class ExcelLoader(DataLoader):
    """Loads a ``.xlsx``/``.xls`` file into a DataFrame via ``pandas.read_excel``."""

    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".xlsx", ".xls"})

    def load(self, source_location: str) -> pd.DataFrame:
        try:
            return pd.read_excel(source_location)
        except Exception as exc:
            raise DatasetCorruptedError(f"Failed to load Excel file '{source_location}': {exc}") from exc
