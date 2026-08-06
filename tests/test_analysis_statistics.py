"""Tests for DescriptiveStatisticsEngine, against small hand-verified DataFrames."""

import pandas as pd

from backend.analysis.statistics.engine import DescriptiveStatisticsEngine


def test_compute_only_includes_numeric_columns() -> None:
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": ["x", "y", "z", "w", "v"]})

    result = DescriptiveStatisticsEngine().compute(df)

    assert set(result.columns) == {"a"}


def test_compute_matches_hand_verified_values() -> None:
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5]})

    stats = DescriptiveStatisticsEngine().compute(df).columns["a"]

    assert stats.mean == 3.0
    assert stats.median == 3.0
    assert stats.std == 1.5811388300841898
    assert stats.variance == 2.5
    assert stats.minimum == 1.0
    assert stats.maximum == 5.0
    assert stats.quartiles == {"q1": 2.0, "q2": 3.0, "q3": 4.0}
    assert stats.percentiles["p5"] == 1.2
    assert stats.percentiles["p95"] == 4.8
    assert stats.distribution_summary["skewness"] == 0.0


def test_compute_handles_multimodal_columns() -> None:
    df = pd.DataFrame({"a": [1, 1, 2, 2, 3]})
    stats = DescriptiveStatisticsEngine().compute(df).columns["a"]
    assert stats.mode == [1.0, 2.0]


def test_compute_handles_a_column_with_missing_values() -> None:
    df = pd.DataFrame({"a": [1.0, None, 3.0, None, 5.0]})
    stats = DescriptiveStatisticsEngine().compute(df).columns["a"]
    assert stats.mean == 3.0
    assert stats.minimum == 1.0
    assert stats.maximum == 5.0


def test_compute_on_empty_dataframe_returns_no_columns() -> None:
    result = DescriptiveStatisticsEngine().compute(pd.DataFrame())
    assert result.columns == {}
