"""RetentionPolicy: configurable, deterministic rules for how much memory to keep.

Every field is optional and defaults to "no limit" — retention is
opt-in, mirroring how ``ApprovalPolicy`` defaults to NEVER (nothing
changes until a caller deliberately configures a limit).
"""

from pydantic import BaseModel, Field


class RetentionPolicy(BaseModel):
    """Deterministic limits ``RetentionEngine`` enforces against the memory store."""

    max_items: int | None = Field(default=None, gt=0)
    max_items_per_type: int | None = Field(default=None, gt=0)
    max_age_days: float | None = Field(default=None, gt=0.0)
