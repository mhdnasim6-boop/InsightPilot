"""ReportSection: one ordered, titled group of content within a report."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from backend.reporting.sections.content_blocks import ContentBlock


class ReportSectionKind(str, Enum):
    """The canonical identity of every section a ``ReportBuilder`` can produce.

    Used as each generated section's ``section_id`` — deterministic and
    predictable, not a random UUID, so template ``required_sections``
    checks and chart/KPI-reference validation can address a section by a
    stable name instead of hunting through titles.
    """

    OVERVIEW = "overview"
    DATASET_SUMMARY = "dataset_summary"
    CLEANING_SUMMARY = "cleaning_summary"
    ANALYSIS = "analysis"
    KPIS = "kpis"
    CHARTS = "charts"
    INSIGHTS = "insights"
    APPENDIX = "appendix"


class ReportSection(BaseModel):
    """One ordered, titled section of a report.

    ``charts``/``tables`` are a denormalized index (chart_ids / table
    captions already present somewhere in ``content_blocks``) kept in
    sync by whichever code appends to ``content_blocks`` — useful for a
    quick "what does this section reference" check without walking every
    block, and for validation.
    """

    section_id: str
    title: str
    order: int
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    charts: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
