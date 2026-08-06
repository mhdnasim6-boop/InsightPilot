"""Structural + confidence validation for a Planner-generated ExecutionPlan."""

from backend.planning.models.plan import ExecutionPlan
from backend.planning.validator.result import (
    IssueSeverity,
    PlanValidationResult,
    ValidationIssue,
)
from backend.planning.validator.validator import PlanValidator


class PlannerPlanValidator:
    """Validates a generated plan's structure (via ``PlanValidator``) and confidence.

    Deliberately uses the lower-level, generic ``PlanValidator`` rather
    than ``PlanningService.validate()``: the latter sources its known
    node names from a live ``OrchestrationService`` graph specifically,
    whereas a Planner's ``available_services`` is a broader, caller-
    declared set (e.g. ``"ingestion"``/``"cleaning"``, which aren't
    orchestration graph nodes at all). Both ultimately reuse the same
    ``PlanValidator`` — no structural-validation logic is duplicated.
    """

    def __init__(self, confidence_threshold: float = 0.5) -> None:
        self._structural_validator = PlanValidator()
        self._confidence_threshold = confidence_threshold

    def validate(self, plan: ExecutionPlan, available_services: set[str], confidence: float) -> PlanValidationResult:
        """Validate a generated plan's structure and confidence.

        Low confidence is recorded as a WARNING (not an error) — it never
        blocks ``is_valid``, so a low-confidence-but-structurally-sound
        plan is still returned, flagged for the caller to review.
        """
        structural_result = self._structural_validator.validate(plan, available_services)
        issues = list(structural_result.issues)

        if confidence < self._confidence_threshold:
            issues.append(
                ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    code="low_confidence",
                    message=(
                        f"Plan confidence ({confidence:.2f}) is below the recommended "
                        f"threshold ({self._confidence_threshold:.2f})."
                    ),
                )
            )

        is_valid = not any(issue.severity == IssueSeverity.ERROR for issue in issues)
        return PlanValidationResult(is_valid=is_valid, issues=issues, execution_order=structural_result.execution_order)
