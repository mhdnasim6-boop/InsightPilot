"""Anomaly detection results — deterministic methods only, no machine learning."""

from pydantic import BaseModel, Field

from backend.analysis.models.common import AnalysisSectionResult


class ColumnAnomalyResult(BaseModel):
    """Z-score and IQR outlier detection for one numeric column."""

    column: str
    zscore_outlier_count: int = 0
    zscore_outlier_percentage: float = 0.0
    zscore_outlier_indices: list[int] = Field(default_factory=list)
    iqr_outlier_count: int = 0
    iqr_outlier_percentage: float = 0.0
    iqr_outlier_indices: list[int] = Field(default_factory=list)


class IsolationForestPlaceholder(BaseModel):
    """Explicitly not implemented in this phase — no machine learning yet."""

    implemented: bool = False
    note: str = (
        "Isolation Forest is a placeholder for a future ML-based anomaly detection "
        "pass; it is not computed in this phase."
    )


class AnomalyAnalysisResult(AnalysisSectionResult):
    """Anomaly detection for the whole dataset.

    ``applicable`` is False (with ``reason`` set) when no numeric columns exist.
    """

    zscore_threshold: float = 3.0
    iqr_multiplier: float = 1.5
    columns: list[ColumnAnomalyResult] = Field(default_factory=list)
    isolation_forest: IsolationForestPlaceholder = Field(default_factory=IsolationForestPlaceholder)
