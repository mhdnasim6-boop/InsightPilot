"""Z-score and IQR outlier detection for every numeric column."""

import pandas as pd

from backend.analysis.models.anomaly import AnomalyAnalysisResult, ColumnAnomalyResult


class AnomalyEngine:
    """Detects outliers via Z-score and IQR — deterministic methods only, no machine learning."""

    def __init__(self, zscore_threshold: float = 3.0, iqr_multiplier: float = 1.5) -> None:
        self._zscore_threshold = zscore_threshold
        self._iqr_multiplier = iqr_multiplier

    def analyze(self, dataframe: pd.DataFrame) -> AnomalyAnalysisResult:
        """Detect outliers in every numeric column, or return Not Applicable if none exist."""
        numeric_columns = dataframe.select_dtypes(include="number").columns
        if len(numeric_columns) == 0:
            return AnomalyAnalysisResult(
                applicable=False,
                reason="No numeric columns available for anomaly detection.",
            )

        columns = [self._analyze_column(dataframe[name]) for name in numeric_columns]
        return AnomalyAnalysisResult(
            applicable=True,
            zscore_threshold=self._zscore_threshold,
            iqr_multiplier=self._iqr_multiplier,
            columns=columns,
        )

    def _analyze_column(self, series: pd.Series) -> ColumnAnomalyResult:
        non_null = series.dropna()
        total = non_null.shape[0]

        zscore_indices = self._zscore_outliers(non_null)
        iqr_indices = self._iqr_outliers(non_null)

        return ColumnAnomalyResult(
            column=str(series.name),
            zscore_outlier_count=len(zscore_indices),
            zscore_outlier_percentage=round(len(zscore_indices) / total * 100, 2) if total > 0 else 0.0,
            zscore_outlier_indices=zscore_indices,
            iqr_outlier_count=len(iqr_indices),
            iqr_outlier_percentage=round(len(iqr_indices) / total * 100, 2) if total > 0 else 0.0,
            iqr_outlier_indices=iqr_indices,
        )

    def _zscore_outliers(self, series: pd.Series) -> list[int]:
        std = series.std()
        if not std or pd.isna(std):
            return []
        mean = series.mean()
        z_scores = (series - mean) / std
        mask = z_scores.abs() > self._zscore_threshold
        return [int(index) for index in series.index[mask]]

    def _iqr_outliers(self, series: pd.Series) -> list[int]:
        if series.empty:
            return []
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            return []
        lower_bound = q1 - self._iqr_multiplier * iqr
        upper_bound = q3 + self._iqr_multiplier * iqr
        mask = (series < lower_bound) | (series > upper_bound)
        return [int(index) for index in series.index[mask]]
