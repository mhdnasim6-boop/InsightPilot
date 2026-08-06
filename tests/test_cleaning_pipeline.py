"""Tests for CleaningPipeline: registration, execution, tracking, and resilience."""

import pandas as pd
import pytest

from backend.cleaning.models.result import CleaningStepRecord
from backend.cleaning.pipeline.default_pipeline import build_default_pipeline
from backend.cleaning.pipeline.pipeline import CleaningPipeline
from backend.cleaning.pipeline.quality_score import compute_quality_score
from backend.cleaning.rules.base import CleaningRule
from backend.cleaning.rules.duplicate_row_rule import DuplicateRowRule
from backend.cleaning.rules.missing_value_rule import MissingValueRule


class _AlwaysFailsRule(CleaningRule):
    name = "always_fails_rule"

    def validate(self, dataframe: pd.DataFrame) -> bool:
        return True

    def apply(self, dataframe: pd.DataFrame) -> tuple[pd.DataFrame, CleaningStepRecord]:
        raise RuntimeError("boom")

    def description(self) -> str:
        return "A rule that always raises, for resilience testing."


def test_register_returns_self_for_chaining() -> None:
    pipeline = CleaningPipeline()
    result = pipeline.register(MissingValueRule())
    assert result is pipeline


def test_execute_runs_registered_rules_and_tracks_steps() -> None:
    df = pd.DataFrame({"a": [1, None, 1]})
    pipeline = CleaningPipeline([MissingValueRule(), DuplicateRowRule()])

    cleaned, result = pipeline.execute(df, "d1")

    assert cleaned.shape[0] == 1  # one None row dropped, then a duplicate removed
    assert [step.rule_name for step in result.steps_applied] == ["missing_value_rule", "duplicate_row_rule"]
    assert result.rows_before == 3
    assert result.rows_after == 1
    assert result.missing_values_before == 1
    assert result.missing_values_after == 0
    assert result.duplicates_removed == 1


def test_execute_skips_rule_with_nothing_to_do_and_warns() -> None:
    df = pd.DataFrame({"a": [1, 2, 3]})  # no missing values
    pipeline = CleaningPipeline([MissingValueRule()])

    _, result = pipeline.execute(df, "d1")

    assert result.steps_applied == []
    assert any("skipped" in warning for warning in result.warnings)


def test_execute_records_a_warning_and_continues_when_a_rule_raises() -> None:
    df = pd.DataFrame({"a": [1, None]})
    pipeline = CleaningPipeline([_AlwaysFailsRule(), MissingValueRule()])

    cleaned, result = pipeline.execute(df, "d1")

    assert cleaned.shape[0] == 1  # MissingValueRule still ran despite the failure before it
    assert any("failed" in warning for warning in result.warnings)
    assert [step.rule_name for step in result.steps_applied] == ["missing_value_rule"]


def test_execute_does_not_mutate_the_input_dataframe() -> None:
    df = pd.DataFrame({"a": [1, None, 1]})
    original_copy = df.copy(deep=True)
    pipeline = CleaningPipeline([MissingValueRule(), DuplicateRowRule()])

    pipeline.execute(df, "d1")

    assert df.equals(original_copy)


def test_execute_produces_a_readable_summary() -> None:
    df = pd.DataFrame({"a": [1, None]})
    pipeline = CleaningPipeline([MissingValueRule()])
    _, result = pipeline.execute(df, "d1")
    assert "Rows:" in result.summary
    assert "Missing values:" in result.summary


def test_compute_quality_score_is_100_with_no_missing_values() -> None:
    assert compute_quality_score(missing_values_after=0, rows_after=10, columns_after=5) == 100.0


def test_compute_quality_score_decreases_with_missing_values() -> None:
    score = compute_quality_score(missing_values_after=5, rows_after=10, columns_after=5)
    assert 0.0 <= score < 100.0


def test_compute_quality_score_handles_empty_dataset() -> None:
    assert compute_quality_score(missing_values_after=0, rows_after=0, columns_after=0) == 0.0


def test_build_default_pipeline_runs_end_to_end() -> None:
    df = pd.DataFrame(
        {
            " Region ": ["East ", " West", "East "],
            "Amount": ["100", "200", "100"],
        }
    )
    pipeline = build_default_pipeline()

    cleaned, result = pipeline.execute(df, "d1")

    assert list(cleaned.columns) == ["region", "amount"]
    assert cleaned.shape[0] == 2  # duplicate row removed
    assert pd.api.types.is_numeric_dtype(cleaned["amount"])
    assert len(result.steps_applied) > 0


@pytest.mark.parametrize("missing,rows,cols", [(0, 5, 0), (0, 0, 5)])
def test_compute_quality_score_zero_denominator_variants(missing: int, rows: int, cols: int) -> None:
    assert compute_quality_score(missing, rows, cols) == 0.0
