"""Export formats an ExecutionTrace can be rendered to. Mirrors ``ReportExportFormat``."""

from enum import Enum


class TraceExportFormat(str, Enum):
    """Supported ExecutionTrace export formats."""

    JSON = "json"
    MARKDOWN = "markdown"
    CSV = "csv"
