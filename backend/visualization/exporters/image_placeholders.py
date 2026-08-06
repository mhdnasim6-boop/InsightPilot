"""PNG/SVG export placeholders — explicitly not implemented in this phase.

Mirrors ``backend.analysis.models.anomaly.IsolationForestPlaceholder``: an
honest, structured "not implemented" rather than a fake render. No PDF
export exists at all (not even as a placeholder).
"""

from backend.visualization.models.chart import ChartSpecification
from backend.visualization.models.placeholder import ExportPlaceholder


class PNGExporter:
    """Explicit placeholder — PNG rendering is not implemented in this phase."""

    def export(self, spec: ChartSpecification) -> ExportPlaceholder:
        """Return a placeholder result for ``spec`` — no PNG is actually rendered."""
        return ExportPlaceholder(
            format="png",
            note="PNG export is a placeholder for a future release; not rendered in this phase.",
        )


class SVGExporter:
    """Explicit placeholder — SVG rendering is not implemented in this phase."""

    def export(self, spec: ChartSpecification) -> ExportPlaceholder:
        """Return a placeholder result for ``spec`` — no SVG is actually rendered."""
        return ExportPlaceholder(
            format="svg",
            note="SVG export is a placeholder for a future release; not rendered in this phase.",
        )
