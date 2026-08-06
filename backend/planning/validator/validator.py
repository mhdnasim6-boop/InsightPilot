"""Structural validation for ExecutionPlan: everything checkable without
running anything — duplicate ids, missing/cyclic dependencies, unknown
node names, and whether a valid execution order even exists.
"""

from backend.planning.models.plan import ExecutionPlan
from backend.planning.models.step import ExecutionStep
from backend.planning.validator.result import (
    IssueSeverity,
    PlanValidationResult,
    ValidationIssue,
)
from backend.planning.validator.topology import CycleDetectedError, topological_order


class PlanValidator:
    """Validates an ExecutionPlan's structure and returns a rich result."""

    def validate(self, plan: ExecutionPlan, known_node_names: set[str] | None = None) -> PlanValidationResult:
        """Validate a plan's steps.

        ``known_node_names``, if given, flags steps whose ``node_name``
        isn't a currently registered orchestration node.
        """
        issues: list[ValidationIssue] = [
            *self._duplicate_step_ids(plan.steps),
            *self._missing_dependencies(plan.steps),
        ]
        if known_node_names is not None:
            issues.extend(self._unknown_node_names(plan.steps, known_node_names))

        execution_order: list[str] | None = None
        if not any(issue.severity == IssueSeverity.ERROR for issue in issues):
            try:
                execution_order = topological_order(plan.steps)
            except CycleDetectedError as exc:
                issues.append(
                    ValidationIssue(severity=IssueSeverity.ERROR, code="cyclic_dependency", message=str(exc))
                )

        is_valid = not any(issue.severity == IssueSeverity.ERROR for issue in issues)
        return PlanValidationResult(is_valid=is_valid, issues=issues, execution_order=execution_order)

    def _duplicate_step_ids(self, steps: list[ExecutionStep]) -> list[ValidationIssue]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for step in steps:
            if step.step_id in seen:
                duplicates.add(step.step_id)
            seen.add(step.step_id)
        return [
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="duplicate_step_id",
                message=f"Step id '{step_id}' is used by more than one step.",
                step_id=step_id,
            )
            for step_id in sorted(duplicates)
        ]

    def _missing_dependencies(self, steps: list[ExecutionStep]) -> list[ValidationIssue]:
        known_ids = {step.step_id for step in steps}
        return [
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="missing_dependency",
                message=f"Step '{step.step_id}' depends on unknown step '{dependency}'.",
                step_id=step.step_id,
            )
            for step in steps
            for dependency in step.dependencies
            if dependency not in known_ids
        ]

    def _unknown_node_names(self, steps: list[ExecutionStep], known_node_names: set[str]) -> list[ValidationIssue]:
        return [
            ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="unknown_node_name",
                message=f"Step '{step.step_id}' references unregistered node '{step.node_name}'.",
                step_id=step.step_id,
            )
            for step in steps
            if step.node_name not in known_node_names
        ]
