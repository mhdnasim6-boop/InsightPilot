"""Computes Pearson/Spearman correlation matrices and flags strong relationships."""

import pandas as pd

from backend.analysis.models.correlation import (
    CorrelationAnalysisResult,
    CorrelationPair,
)
from backend.ingestion.metadata.json_safe import to_jsonable


class CorrelationEngine:
    """Computes correlation matrices and strong positive/negative pairs for numeric columns."""

    def __init__(self, strong_threshold: float = 0.7) -> None:
        self._strong_threshold = strong_threshold

    def analyze(self, dataframe: pd.DataFrame) -> CorrelationAnalysisResult:
        """Analyze correlations among numeric columns, or return Not Applicable if fewer than two exist."""
        numeric = dataframe.select_dtypes(include="number")
        columns = list(numeric.columns)

        if len(columns) < 2:
            return CorrelationAnalysisResult(
                applicable=False,
                reason="Fewer than two numeric columns available for correlation analysis.",
            )

        pearson = numeric.corr(method="pearson")
        spearman = numeric.corr(method="spearman")
        pearson_matrix = to_jsonable(pearson.to_dict())
        spearman_matrix = to_jsonable(spearman.to_dict())

        strong_positive: list[CorrelationPair] = []
        strong_negative: list[CorrelationPair] = []
        for i, column_a in enumerate(columns):
            for column_b in columns[i + 1 :]:
                pearson_value = pearson_matrix.get(column_a, {}).get(column_b)
                spearman_value = spearman_matrix.get(column_a, {}).get(column_b)
                if pearson_value is None:
                    continue
                pair = CorrelationPair(
                    column_a=column_a, column_b=column_b, pearson=pearson_value, spearman=spearman_value
                )
                if pearson_value >= self._strong_threshold:
                    strong_positive.append(pair)
                elif pearson_value <= -self._strong_threshold:
                    strong_negative.append(pair)

        return CorrelationAnalysisResult(
            applicable=True,
            columns=columns,
            pearson_matrix=pearson_matrix,
            spearman_matrix=spearman_matrix,
            strong_positive=strong_positive,
            strong_negative=strong_negative,
        )
