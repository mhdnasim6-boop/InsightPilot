"""Rich validation results for dataset ingestion."""

from enum import Enum

from pydantic import BaseModel, Field


class IssueSeverity(str, Enum):
    """Severity of a single validation finding."""

    ERROR = "error"
    WARNING = "warning"


class ValidationIssue(BaseModel):
    """A single validation finding."""

    severity: IssueSeverity
    code: str
    message: str


class DatasetValidationResult(BaseModel):
    """The full outcome of validating a source and/or a loaded DataFrame."""

    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        """Issues severe enough to block ingestion."""
        return [issue for issue in self.issues if issue.severity == IssueSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Issues that don't block ingestion but are worth surfacing."""
        return [issue for issue in self.issues if issue.severity == IssueSeverity.WARNING]
