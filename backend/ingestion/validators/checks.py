"""Shared, stateless validation checks.

Used both by ``DataLoader``'s default ``validate()`` (a narrow, loader-
specific pre-flight check) and by ``DatasetValidator`` (the full,
registry-aware check) — one implementation of each rule, not two.
"""

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from backend.ingestion.validators.result import IssueSeverity, ValidationIssue


def check_extension(source_location: str, known_extensions: Iterable[str]) -> list[ValidationIssue]:
    """Flag a source whose extension isn't in ``known_extensions``."""
    extension = Path(source_location).suffix.lower()
    if extension not in set(known_extensions):
        return [
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="unsupported_extension",
                message=f"Unsupported file extension: '{extension}'.",
            )
        ]
    return []


def check_source_file(source_location: str) -> list[ValidationIssue]:
    """Flag a source file that doesn't exist or is empty (zero bytes)."""
    path = Path(source_location)
    if not path.exists():
        return [
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="source_not_found",
                message=f"Source file not found: '{source_location}'.",
            )
        ]
    if path.stat().st_size == 0:
        return [
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="empty_file",
                message=f"Source file is empty: '{source_location}'.",
            )
        ]
    return []


def check_dataframe(dataframe: pd.DataFrame) -> list[ValidationIssue]:
    """Flag a loaded DataFrame with no columns, no rows, or duplicate column names.

    Duplicate-column detection operates on the already-loaded DataFrame:
    pandas auto-renames duplicate CSV/Excel headers on read (``a`` ->
    ``a.1``), so this mainly catches duplicates from sources that don't go
    through that mangling (e.g. a future SQL/API loader).
    """
    issues: list[ValidationIssue] = []
    if dataframe.shape[1] == 0:
        issues.append(
            ValidationIssue(severity=IssueSeverity.ERROR, code="invalid_schema", message="Dataset has no columns.")
        )
    if dataframe.shape[0] == 0:
        issues.append(
            ValidationIssue(severity=IssueSeverity.WARNING, code="empty_dataset", message="Dataset has no rows.")
        )
    if dataframe.columns.duplicated().any():
        duplicates = sorted(set(dataframe.columns[dataframe.columns.duplicated()]))
        issues.append(
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="duplicate_columns",
                message=f"Dataset has duplicate column names: {duplicates}.",
            )
        )
    return issues
