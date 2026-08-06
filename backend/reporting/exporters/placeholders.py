"""PDF/Word/PowerPoint export placeholders — explicitly not implemented in this phase.

Reuses ``backend.visualization.models.placeholder.ExportPlaceholder``
directly rather than redefining an equivalent class: a structured
"not implemented" result is a generic concept, not visualization-specific
— the same honest-placeholder pattern as
``backend.visualization.exporters.image_placeholders.PNGExporter``/
``SVGExporter``. No PDF rendering implementation exists at all.
"""

from backend.reporting.models.report_document import ReportDocument
from backend.visualization.models.placeholder import ExportPlaceholder


class PDFReportExporter:
    """Explicit placeholder — PDF rendering is not implemented in this phase."""

    def export(self, document: ReportDocument) -> ExportPlaceholder:
        """Return a placeholder result for ``document`` — no PDF is actually rendered."""
        return ExportPlaceholder(
            format="pdf", note="PDF export is a placeholder for a future release; not rendered in this phase."
        )


class WordReportExporter:
    """Explicit placeholder — Word rendering is not implemented in this phase."""

    def export(self, document: ReportDocument) -> ExportPlaceholder:
        """Return a placeholder result for ``document`` — no Word document is actually rendered."""
        return ExportPlaceholder(
            format="word", note="Word export is a placeholder for a future release; not rendered in this phase."
        )


class PowerPointReportExporter:
    """Explicit placeholder — PowerPoint rendering is not implemented in this phase."""

    def export(self, document: ReportDocument) -> ExportPlaceholder:
        """Return a placeholder result for ``document`` — no PowerPoint deck is actually rendered."""
        return ExportPlaceholder(
            format="powerpoint",
            note="PowerPoint export is a placeholder for a future release; not rendered in this phase.",
        )
