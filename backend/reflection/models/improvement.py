"""Improvement: one longer-term, structural "what could be improved next time"
observation — broader than a single Recommendation (a concrete action),
this names an *area* (e.g. "efficiency", "approval_policy") and the
expected effect of addressing it.
"""

from pydantic import BaseModel, ConfigDict


class Improvement(BaseModel):
    """One structural improvement area surfaced by reflecting on an execution."""

    model_config = ConfigDict(frozen=True)

    improvement_id: str
    area: str
    description: str
    expected_impact: str
