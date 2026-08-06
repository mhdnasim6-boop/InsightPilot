"""TraceExporter: dispatches an ExecutionTrace export to the requested format.

Mirrors ``ReportService``'s own ``dict[Format, exporter.export]``
dispatch table — no format-specific branching anywhere else.
"""

from collections.abc import Callable

from backend.observability.exceptions import UnsupportedExportFormatError
from backend.observability.exporters.csv_exporter import CSVTraceExporter
from backend.observability.exporters.json_exporter import JSONTraceExporter
from backend.observability.exporters.markdown_exporter import MarkdownTraceExporter
from backend.observability.models.execution_trace import ExecutionTrace
from backend.observability.models.export_format import TraceExportFormat

_ExporterFn = Callable[[ExecutionTrace], str]


class TraceExporter:
    """Renders an ExecutionTrace to JSON, Markdown, or CSV."""

    def __init__(
        self,
        json_exporter: JSONTraceExporter | None = None,
        markdown_exporter: MarkdownTraceExporter | None = None,
        csv_exporter: CSVTraceExporter | None = None,
    ) -> None:
        self._exporters: dict[TraceExportFormat, _ExporterFn] = {
            TraceExportFormat.JSON: (json_exporter or JSONTraceExporter()).export,
            TraceExportFormat.MARKDOWN: (markdown_exporter or MarkdownTraceExporter()).export,
            TraceExportFormat.CSV: (csv_exporter or CSVTraceExporter()).export,
        }

    def export(self, trace: ExecutionTrace, export_format: TraceExportFormat) -> str:
        """Render ``trace`` to ``export_format``. Raises UnsupportedExportFormatError otherwise."""
        exporter = self._exporters.get(export_format)
        if exporter is None:
            raise UnsupportedExportFormatError(f"Unsupported trace export format: '{export_format}'.")
        return exporter(trace)
