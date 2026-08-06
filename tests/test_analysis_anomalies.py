"""Tests for AnomalyEngine: deterministic Z-score and IQR outlier detection."""

import pandas as pd

from backend.analysis.anomalies.engine import AnomalyEngine


def test_anomaly_not_applicable_without_numeric_columns() -> None:
    df = pd.DataFrame({"region": ["East", "West"]})
    result = AnomalyEngine().analyze(df)
    assert result.applicable is False
    assert result.reason is not None


def test_iqr_detects_a_clear_outlier() -> None:
    df = pd.DataFrame({"amount": [10, 11, 9, 10, 11, 9, 10, 300]})

    result = AnomalyEngine().analyze(df)

    column = result.columns[0]
    assert column.iqr_outlier_count == 1
    assert 7 in column.iqr_outlier_indices


def test_zscore_detects_a_sufficiently_extreme_outlier() -> None:
    # A single outlier's z-score is mathematically capped by sample size
    # (max |z| <= sqrt(n-1)); this dataset is large enough (n=17) for a
    # genuine z > 3.0 outlier while remaining small and hand-verifiable.
    values = [10, 11, 9, 10, 11, 9, 10, 11, 9, 10, 11, 9, 10, 11, 9, 10, 200]
    df = pd.DataFrame({"amount": values})

    result = AnomalyEngine().analyze(df)

    column = result.columns[0]
    assert column.zscore_outlier_count == 1
    assert column.zscore_outlier_indices == [16]


def test_constant_column_produces_zero_outliers_without_crashing() -> None:
    df = pd.DataFrame({"amount": [5, 5, 5, 5]})
    result = AnomalyEngine().analyze(df)
    column = result.columns[0]
    assert column.zscore_outlier_count == 0
    assert column.iqr_outlier_count == 0


def test_custom_thresholds_change_sensitivity() -> None:
    df = pd.DataFrame({"amount": [10, 11, 9, 10, 11, 9, 10, 30]})

    lenient = AnomalyEngine(zscore_threshold=1.0).analyze(df)
    strict = AnomalyEngine(zscore_threshold=5.0).analyze(df)

    assert lenient.columns[0].zscore_outlier_count >= strict.columns[0].zscore_outlier_count


def test_isolation_forest_is_reported_as_a_placeholder() -> None:
    df = pd.DataFrame({"amount": [1, 2, 3]})
    result = AnomalyEngine().analyze(df)
    assert result.isolation_forest.implemented is False
