"""Tests for AggregationEngine: group-by and pivot-style summaries."""

import pandas as pd

from backend.analysis.aggregations.engine import AggregationEngine
from backend.analysis.models.aggregation import AggregationFunction


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "region": ["East", "East", "West", "West"],
            "category": ["a", "b", "a", "b"],
            "amount": [100, 50, 10, 20],
        }
    )


def test_group_by_sum() -> None:
    result = AggregationEngine().group_by(_df(), "region", "amount", AggregationFunction.SUM)
    assert result.results == {"East": 150, "West": 30}


def test_group_by_average() -> None:
    result = AggregationEngine().group_by(_df(), "region", "amount", AggregationFunction.AVERAGE)
    assert result.results == {"East": 75.0, "West": 15.0}


def test_group_by_median_min_max() -> None:
    engine = AggregationEngine()
    assert engine.group_by(_df(), "region", "amount", AggregationFunction.MEDIAN).results == {
        "East": 75.0,
        "West": 15.0,
    }
    assert engine.group_by(_df(), "region", "amount", AggregationFunction.MINIMUM).results == {
        "East": 50,
        "West": 10,
    }
    assert engine.group_by(_df(), "region", "amount", AggregationFunction.MAXIMUM).results == {
        "East": 100,
        "West": 20,
    }


def test_group_by_count_with_value_column() -> None:
    result = AggregationEngine().group_by(_df(), "region", "amount", AggregationFunction.COUNT)
    assert result.results == {"East": 2, "West": 2}


def test_group_by_count_without_value_column_counts_rows() -> None:
    result = AggregationEngine().group_by(_df(), "region", None, AggregationFunction.COUNT)
    assert result.results == {"East": 2, "West": 2}


def test_pivot_sum() -> None:
    result = AggregationEngine().pivot(_df(), "region", "category", "amount", AggregationFunction.SUM)
    assert result.table["East"]["a"] == 100
    assert result.table["East"]["b"] == 50
    assert result.table["West"]["a"] == 10
    assert result.table["West"]["b"] == 20


def test_pivot_missing_combination_is_none() -> None:
    df = pd.DataFrame({"region": ["East", "West"], "category": ["a", "b"], "amount": [100, 20]})
    result = AggregationEngine().pivot(df, "region", "category", "amount", AggregationFunction.SUM)
    assert result.table["East"]["b"] is None
    assert result.table["West"]["a"] is None
