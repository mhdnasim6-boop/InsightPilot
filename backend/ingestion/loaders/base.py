"""Common interface every data loader must implement.

Mirrors ``backend.orchestration.nodes.base.OrchestrationNode``: one
required method (``load``) drives every future loader; ``validate()``/
``metadata()`` have sensible defaults so simple loaders (CSV, Excel) don't
need to override them.
"""

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from backend.ingestion.validators.checks import check_extension, check_source_file
from backend.ingestion.validators.result import DatasetValidationResult, IssueSeverity


class DataLoader(ABC):
    """Contract every data loader (implemented or future) must satisfy."""

    @abstractmethod
    def load(self, source_location: str) -> pd.DataFrame:
        """Load a source into a DataFrame. No cleaning or transformation."""

    @abstractmethod
    def supported_extensions(self) -> frozenset[str]:
        """Return the file extensions (lowercase, with the dot) this loader handles."""

    def validate(self, source_location: str) -> DatasetValidationResult:
        """Check this source is one this loader can attempt to load. Default: extension + existence/non-empty."""
        issues = [
            *check_extension(source_location, self.supported_extensions()),
            *check_source_file(source_location),
        ]
        is_valid = not any(issue.severity == IssueSeverity.ERROR for issue in issues)
        return DatasetValidationResult(is_valid=is_valid, issues=issues)

    def metadata(self) -> dict[str, Any]:
        """Describe this loader for introspection. Default: its name and supported extensions."""
        return {"name": type(self).__name__, "supported_extensions": sorted(self.supported_extensions())}
