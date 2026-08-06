"""Layouts: purely organizational groupings of already-generated charts.

A layout never creates, modifies, or renders a chart — it only references
chart IDs and arranges them into named, ordered sections.
"""

from enum import Enum

from pydantic import BaseModel, Field


class LayoutType(str, Enum):
    """The four supported layout templates."""

    EXECUTIVE_SUMMARY = "executive_summary"
    DETAILED_ANALYSIS = "detailed_analysis"
    KPI_DASHBOARD = "kpi_dashboard"
    COMPARISON_DASHBOARD = "comparison_dashboard"


class LayoutSection(BaseModel):
    """One named, ordered group of charts within a layout."""

    title: str
    chart_ids: list[str] = Field(default_factory=list)
    columns: int = 2


class Layout(BaseModel):
    """A named arrangement of chart sections."""

    layout_type: LayoutType
    sections: list[LayoutSection] = Field(default_factory=list)
