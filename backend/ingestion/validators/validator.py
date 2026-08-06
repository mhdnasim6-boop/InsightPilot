"""Full, registry-aware dataset validation."""

from collections.abc import Iterable

import pandas as pd

from backend.ingestion.validators.checks import (
    check_dataframe,
    check_extension,
    check_source_file,
)
from backend.ingestion.validators.result import (
    DatasetValidationResult,
    IssueSeverity,
    ValidationIssue,
)


class DatasetValidator:
    """Validates a source location and, once loaded, its DataFrame."""

    def validate(
        self,
        source_location: str,
        known_extensions: Iterable[str],
        dataframe: pd.DataFrame | None = None,
    ) -> DatasetValidationResult:
        """Validate a source's extension/existence, and its DataFrame if already loaded."""
        issues: list[ValidationIssue] = [
            *check_extension(source_location, known_extensions),
            *check_source_file(source_location),
        ]
        if dataframe is not None:
            issues.extend(check_dataframe(dataframe))

        is_valid = not any(issue.severity == IssueSeverity.ERROR for issue in issues)
        return DatasetValidationResult(is_valid=is_valid, issues=issues)

    def validate_dataframe(self, dataframe: pd.DataFrame) -> DatasetValidationResult:
        """Validate an already-loaded DataFrame with no source file to check.

        The non-file counterpart to :meth:`validate` — for a SQL query
        result (or any other future non-file source) there is no
        extension or on-disk path to check, only the DataFrame's shape.
        """
        issues = check_dataframe(dataframe)
        is_valid = not any(issue.severity == IssueSeverity.ERROR for issue in issues)
        return DatasetValidationResult(is_valid=is_valid, issues=issues)
