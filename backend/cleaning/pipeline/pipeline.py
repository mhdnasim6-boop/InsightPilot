"""Runs a registered sequence of independent CleaningRules against a DataFrame.

No AI: rule selection and ordering are explicit (caller-registered), never
inferred from the data.
"""

import pandas as pd
from loguru import logger

from backend.cleaning.models.result import CleaningResult, CleaningStepRecord
from backend.cleaning.pipeline.quality_score import compute_quality_score
from backend.cleaning.rules.base import CleaningRule
from backend.cleaning.validators.post_clean import validate_cleaned_dataframe
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class CleaningPipeline:
    """Registers and executes CleaningRules in order, producing a CleaningResult.

    Rules are independent: one rule failing is recorded as a warning and
    skipped, never allowed to abort the rules registered after it.
    """

    def __init__(self, rules: list[CleaningRule] | None = None) -> None:
        self._rules: list[CleaningRule] = list(rules) if rules else []

    def register(self, rule: CleaningRule) -> "CleaningPipeline":
        """Register a rule to run, in the order registered."""
        self._rules.append(rule)
        return self

    def execute(self, dataframe: pd.DataFrame, dataset_id: str) -> tuple[pd.DataFrame, CleaningResult]:
        """Run every registered rule in order, producing the cleaned DataFrame and a CleaningResult."""
        rows_before = dataframe.shape[0]
        columns_before = dataframe.shape[1]
        missing_values_before = int(dataframe.isna().to_numpy().sum())

        current = dataframe
        steps: list[CleaningStepRecord] = []
        warnings: list[str] = []
        columns_modified: set[str] = set()

        for rule in self._rules:
            if not rule.validate(current):
                warnings.append(f"Rule '{rule.name}' skipped: nothing to do.")
                continue
            try:
                updated, step = rule.apply(current)
            except Exception as exc:  # noqa: BLE001 - one independent rule failing must not abort the others
                logger.warning("Cleaning rule '{}' failed: {}", rule.name, exc)
                warnings.append(f"Rule '{rule.name}' failed: {exc}")
                continue
            current = updated
            steps.append(step)
            columns_modified.update(step.columns_affected)

        warnings.extend(validate_cleaned_dataframe(current))

        rows_after = current.shape[0]
        columns_after = current.shape[1]
        missing_values_after = int(current.isna().to_numpy().sum())
        duplicates_removed = sum(step.details.get("duplicates_removed", 0) for step in steps)
        quality_score = compute_quality_score(missing_values_after, rows_after, columns_after)

        result = CleaningResult(
            cleaning_id=generate_id(),
            dataset_id=dataset_id,
            steps_applied=steps,
            rows_before=rows_before,
            rows_after=rows_after,
            columns_before=columns_before,
            columns_after=columns_after,
            missing_values_before=missing_values_before,
            missing_values_after=missing_values_after,
            duplicates_removed=duplicates_removed,
            columns_modified=sorted(columns_modified),
            warnings=warnings,
            summary=self._build_summary(
                len(steps), rows_before, rows_after, missing_values_before, missing_values_after, duplicates_removed
            ),
            quality_score=quality_score,
            metadata={},
            created_at=utc_now(),
        )
        return current, result

    def _build_summary(
        self,
        steps_applied: int,
        rows_before: int,
        rows_after: int,
        missing_before: int,
        missing_after: int,
        duplicates_removed: int,
    ) -> str:
        return (
            f"Applied {steps_applied} of {len(self._rules)} registered rule(s). "
            f"Rows: {rows_before} -> {rows_after}. "
            f"Missing values: {missing_before} -> {missing_after}. "
            f"Duplicates removed: {duplicates_removed}."
        )
