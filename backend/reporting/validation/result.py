"""Result of validating a ReportDocument.

Mirrors ``backend.ingestion.validators.result.DatasetValidationResult``'s
shape exactly, reusing ``ValidationIssue``/``IssueSeverity`` directly — a
structured validation finding is a generic concept, not report-specific.
"""

from pydantic import BaseModel, Field

from backend.ingestion.validators.result import IssueSeverity, ValidationIssue


class ReportValidationResult(BaseModel):
    """The full outcome of validating a ``ReportDocument``."""

    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        """Issues severe enough to block export."""
        return [issue for issue in self.issues if issue.severity == IssueSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Issues that don't block export but are worth surfacing."""
        return [issue for issue in self.issues if issue.severity == IssueSeverity.WARNING]
