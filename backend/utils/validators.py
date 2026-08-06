"""Reusable, stateless validation helpers."""

from pathlib import Path

from backend.core.constants import SUPPORTED_FILE_TYPES


def is_supported_file_type(filename: str) -> bool:
    """Check whether a filename's extension is one InsightPilot can accept."""
    return Path(filename).suffix.lower() in SUPPORTED_FILE_TYPES
