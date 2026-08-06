"""Shared base for analysis sections that may not apply to a given dataset
(trends with no time column, correlations with fewer than two numeric
columns, anomalies with no numeric columns).
"""

from pydantic import BaseModel


class AnalysisSectionResult(BaseModel):
    """Base for any analysis section that can be structurally "Not Applicable"."""

    applicable: bool = True
    reason: str | None = None
