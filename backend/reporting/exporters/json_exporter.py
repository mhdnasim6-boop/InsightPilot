"""JSON export for a ReportDocument.

Trivial by design: ``ReportDocument`` is already a plain, self-contained
Pydantic model — exporting it to JSON is just serialization, proof that
the document alone is enough for any downstream consumer.
"""

from backend.reporting.models.report_document import ReportDocument


class JSONReportExporter:
    """Serializes a ReportDocument to a stable, indented JSON string."""

    def export(self, document: ReportDocument) -> str:
        """Return ``document`` as an indented JSON string."""
        return document.model_dump_json(indent=2)
