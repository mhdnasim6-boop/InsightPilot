"""Tests for CorrelationEngine."""

import pandas as pd

from backend.analysis.correlations.engine import CorrelationEngine


def test_correlation_not_applicable_with_fewer_than_two_numeric_columns() -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "region": ["x", "y", "z"]})
    result = CorrelationEngine().analyze(df)
    assert result.applicable is False
    assert result.reason is not None


def test_correlation_matrix_and_strong_pairs() -> None:
    df = pd.DataFrame(
        {
            "a": [1, 2, 3, 4, 5],
            "b": [2, 4, 6, 8, 10],  # perfectly positively correlated with a
            "c": [10, 8, 6, 4, 2],  # perfectly negatively correlated with a and b
        }
    )

    result = CorrelationEngine().analyze(df)

    assert result.applicable is True
    assert set(result.columns) == {"a", "b", "c"}
    assert result.pearson_matrix["a"]["b"] == 1.0
    assert result.pearson_matrix["a"]["c"] == -1.0

    positive_pairs = {(pair.column_a, pair.column_b) for pair in result.strong_positive}
    negative_pairs = {(pair.column_a, pair.column_b) for pair in result.strong_negative}
    assert ("a", "b") in positive_pairs
    assert ("a", "c") in negative_pairs
    assert ("b", "c") in negative_pairs


def test_correlation_respects_a_custom_threshold() -> None:
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [1, 2, 3, 5]})  # strongly but not perfectly correlated

    lenient = CorrelationEngine(strong_threshold=0.5).analyze(df)
    strict = CorrelationEngine(strong_threshold=0.999).analyze(df)

    assert len(lenient.strong_positive) == 1
    assert len(strict.strong_positive) == 0
