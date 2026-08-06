"""Rich validation results for ExecutionPlan validation."""

from enum import Enum

from pydantic import BaseModel, Field


class IssueSeverity(str, Enum):
    """Severity of a single validation finding."""

    ERROR = "error"
    WARNING = "warning"


class ValidationIssue(BaseModel):
    """A single validation finding, tied to a step where applicable."""

    severity: IssueSeverity
    code: str
    message: str
    step_id: str | None = None


class PlanValidationResult(BaseModel):
    """The full outcome of validating a plan.

    ``execution_order`` is only populated when the plan is structurally
    sound (no duplicate ids, no missing/cyclic dependencies) — it's the
    order ``PlanExecutor`` would run the steps in.
    """

    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    execution_order: list[str] | None = None

    @property
    def errors(self) -> list[ValidationIssue]:
        """Issues severe enough to block execution."""
        return [issue for issue in self.issues if issue.severity == IssueSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Issues that don't block execution but are worth surfacing."""
        return [issue for issue in self.issues if issue.severity == IssueSeverity.WARNING]
