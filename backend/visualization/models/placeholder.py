"""Shared shape for explicitly-not-implemented export formats.

Mirrors ``backend.analysis.models.anomaly.IsolationForestPlaceholder`` —
an honest, structured "not implemented" rather than a fake success.
"""

from pydantic import BaseModel


class ExportPlaceholder(BaseModel):
    """Reported by an export format that is recognized but not implemented yet."""

    implemented: bool = False
    format: str
    note: str
