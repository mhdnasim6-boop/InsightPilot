"""Tests for time-column detection and TrendEngine."""

import pandas as pd

from backend.analysis.trends.detection import detect_time_column
from backend.analysis.trends.engine import TrendEngine


def test_detect_time_column_prefers_real_datetime_dtype() -> None:
    df = pd.DataFrame({"created": pd.to_datetime(["2024-01-01", "2024-02-01"]), "note": ["a", "b"]})
    assert detect_time_column(df) == "created"


def test_detect_time_column_falls_back_to_name_keyword() -> None:
    df = pd.DataFrame({"date": ["2024-01-01", "2024-02-01"], "amount": [1, 2]})
    assert detect_time_column(df) == "date"


def test_detect_time_column_returns_none_when_no_candidate() -> None:
    df = pd.DataFrame({"region": ["East", "West"], "amount": [1, 2]})
    assert detect_time_column(df) is None


def test_trend_engine_returns_not_applicable_without_a_time_column() -> None:
    df = pd.DataFrame({"region": ["East", "West"], "amount": [1, 2]})
    result = TrendEngine().analyze(df)
    assert result.applicable is False
    assert result.reason is not None
    assert result.series == []


def test_trend_engine_computes_series_for_every_numeric_column() -> None:
    df = pd.DataFrame({"date": ["2024-01-01", "2024-02-01", "2024-03-01"], "amount": [100, 120, 150]})

    result = TrendEngine(window=2).analyze(df)

    assert result.applicable is True
    assert result.time_column == "date"
    assert len(result.series) == 1

    series = result.series[0]
    assert series.column == "amount"
    assert series.rolling_average == [None, 110.0, 135.0]
    assert series.running_total == [100.0, 220.0, 370.0]
    assert series.growth_rate == 50.0  # (150 - 100) / 100 * 100


def test_trend_engine_sorts_by_time_column_before_computing() -> None:
    df = pd.DataFrame({"date": ["2024-03-01", "2024-01-01", "2024-02-01"], "amount": [150, 100, 120]})

    result = TrendEngine().analyze(df)

    assert result.series[0].running_total == [100.0, 220.0, 370.0]


def test_trend_engine_growth_rate_is_none_for_a_single_data_point() -> None:
    df = pd.DataFrame({"date": ["2024-01-01"], "amount": [100]})
    result = TrendEngine().analyze(df)
    assert result.series[0].growth_rate is None
