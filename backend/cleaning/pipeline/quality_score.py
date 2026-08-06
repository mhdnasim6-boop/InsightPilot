"""Computes a deterministic, explainable post-cleaning quality score.

Not AI: a simple, documented formula over already-computed facts. 100
means no missing values remain in the cleaned dataset; lower scores mean
more residual missing data.
"""


def compute_quality_score(missing_values_after: int, rows_after: int, columns_after: int) -> float:
    """Return a 0-100 quality score for a cleaned dataset's residual missing-value rate."""
    total_cells = rows_after * columns_after
    if total_cells <= 0:
        return 0.0
    missing_percentage = (missing_values_after / total_cells) * 100
    return round(max(0.0, 100.0 - missing_percentage), 2)
