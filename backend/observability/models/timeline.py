"""TimelineEntry: one chronological row in a trace's Execution Timeline.

A read-side projection, not a stored model — ``build_timeline()``
derives it fresh from an already-fetched ``ExecutionTrace`` by merging
its agent/tool/AI/approval records into one time-ordered sequence.
``status`` is a plain string because the four record kinds carry
different status types (``ExecutionStatus`` for agent/tool records,
``ApprovalStatus`` for approvals, and AI calls — which InsightPilot
only ever records on success — are always reported "completed").
"""

from datetime import datetime

from pydantic import BaseModel


class TimelineEntry(BaseModel):
    """One agent/tool/AI-call/approval event, positioned on a trace's timeline."""

    kind: str
    name: str
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None
    status: str
