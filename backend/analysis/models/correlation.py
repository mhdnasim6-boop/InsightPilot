"""Correlation analysis results."""

from pydantic import BaseModel, Field

from backend.analysis.models.common import AnalysisSectionResult


class CorrelationPair(BaseModel):
    """One pair of numeric columns and their correlation coefficients."""

    column_a: str
    column_b: str
    pearson: float | None = None
    spearman: float | None = None


class CorrelationAnalysisResult(AnalysisSectionResult):
    """Correlation analysis for the whole dataset.

    ``applicable`` is False (with ``reason`` set) when fewer than two
    numeric columns exist.
    """

    columns: list[str] = Field(default_factory=list)
    pearson_matrix: dict[str, dict[str, float | None]] = Field(default_factory=dict)
    spearman_matrix: dict[str, dict[str, float | None]] = Field(default_factory=dict)
    strong_positive: list[CorrelationPair] = Field(default_factory=list)
    strong_negative: list[CorrelationPair] = Field(default_factory=list)
