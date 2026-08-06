"""ReportDocument: the single, self-contained representation of a generated report.

Every future exporter (PDF, Word, PowerPoint) and every future AI
executive-summary writer consumes a ``ReportDocument`` — never
``AnalysisResult``/``VisualizationResult`` directly, and never a
DataFrame. That is what makes it portable: a document exported to JSON
today must still be fully renderable by a process with no access to the
original analysis/visualization objects tomorrow.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from backend.reporting.sections.section import ReportSection


class ReportExportFormat(str, Enum):
    """Every export format the reporting framework recognizes, implemented or not."""

    JSON = "json"
    MARKDOWN = "markdown"
    PDF = "pdf"
    WORD = "word"
    POWERPOINT = "powerpoint"


class TableOfContentsEntry(BaseModel):
    """One navigable entry in a report's table of contents."""

    section_id: str
    title: str
    order: int


class ReportDocument(BaseModel):
    """The complete, structured output of generating one report."""

    report_id: str
    title: str
    subtitle: str | None = None
    generated_at: datetime
    author: str | None = None
    version: str = "1.0"
    theme: str = "corporate"
    table_of_contents: list[TableOfContentsEntry] = Field(default_factory=list)
    sections: list[ReportSection] = Field(default_factory=list)
    appendices: list[ReportSection] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
