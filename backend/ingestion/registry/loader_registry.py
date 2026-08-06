"""Maps a file extension to a loader.

Mirrors ``backend.ai.providers.factory.ProviderFactory`` exactly: a plain
dict dispatch table (no if/else chains) plus a frozenset of extensions
that are recognized concepts (PDF, Word, PowerPoint) with no loader
implementation yet. Adding a real loader for one of those later means
moving its extension from ``_PLACEHOLDER_EXTENSIONS`` into ``_REGISTRY``
— nothing else in the ingestion layer changes.
"""

from collections.abc import Callable

from backend.ingestion.exceptions.errors import (
    SourceNotImplementedError,
    UnsupportedSourceError,
)
from backend.ingestion.loaders.base import DataLoader
from backend.ingestion.loaders.csv_loader import CSVLoader
from backend.ingestion.loaders.excel_loader import ExcelLoader

_REGISTRY: dict[str, Callable[[], DataLoader]] = {
    ".csv": CSVLoader,
    ".xlsx": ExcelLoader,
    ".xls": ExcelLoader,
}

# Recognized source-file extensions with no loader implementation in this phase.
_PLACEHOLDER_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx", ".pptx"})


class LoaderRegistry:
    """Resolves a file extension to a ``DataLoader`` instance."""

    def get_loader(self, extension: str) -> DataLoader:
        """Return a loader for ``extension``.

        Raises ``SourceNotImplementedError`` for a recognized-but-not-yet-
        implemented extension, or ``UnsupportedSourceError`` for one
        InsightPilot doesn't recognize at all.
        """
        ext = extension.lower()
        if ext in _PLACEHOLDER_EXTENSIONS:
            raise SourceNotImplementedError(f"Source type for '{ext}' is recognized but not implemented yet.")

        builder = _REGISTRY.get(ext)
        if builder is None:
            raise UnsupportedSourceError(f"Unsupported file extension: '{ext}'.")
        return builder()

    def known_extensions(self) -> frozenset[str]:
        """Every extension InsightPilot recognizes, implemented or not."""
        return frozenset(_REGISTRY) | _PLACEHOLDER_EXTENSIONS

    def available_extensions(self) -> list[str]:
        """Extensions that can actually be loaded today."""
        return sorted(_REGISTRY)
