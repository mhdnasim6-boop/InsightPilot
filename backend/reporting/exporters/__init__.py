"""Converts a self-contained ``ReportDocument`` into an output form: real JSON/Markdown
strings, or an explicit PDF/Word/PowerPoint placeholder (no PDF rendering yet).
"""

from backend.reporting.exporters.json_exporter import JSONReportExporter
from backend.reporting.exporters.markdown_exporter import MarkdownReportExporter
from backend.reporting.exporters.placeholders import (
    PDFReportExporter,
    PowerPointReportExporter,
    WordReportExporter,
)

__all__ = [
    "JSONReportExporter",
    "MarkdownReportExporter",
    "PDFReportExporter",
    "PowerPointReportExporter",
    "WordReportExporter",
]
