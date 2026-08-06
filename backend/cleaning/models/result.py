"""The result of running a CleaningPipeline: a full audit trail of what happened."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CleaningStepRecord(BaseModel):
    """A record of one rule's execution within a cleaning run."""

    rule_name: str
    description: str
    rows_before: int
    rows_after: int
    columns_affected: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class CleaningResult(BaseModel):
    """A complete report of one ``CleaningPipeline.execute()`` run.

    Not immutable like ``ExecutionPlan``: it's a finished report, not a
    lifecycle state machine, so there's nothing to transition through —
    consistent with ``BusinessDataset`` also being a plain (non-frozen)
    model in this codebase.
    """

    cleaning_id: str
    dataset_id: str
    steps_applied: list[CleaningStepRecord] = Field(default_factory=list)
    rows_before: int
    rows_after: int
    columns_before: int
    columns_after: int
    missing_values_before: int
    missing_values_after: int
    duplicates_removed: int
    columns_modified: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str
    quality_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
