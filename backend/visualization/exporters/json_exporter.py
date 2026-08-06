"""JSON export for a ChartSpecification.

Trivial by design: ``ChartSpecification`` is already a plain, rendering-
independent Pydantic model — exporting it to JSON is just serialization,
proof that the spec alone is enough for any downstream consumer.
"""

from backend.visualization.models.chart import ChartSpecification


class JSONExporter:
    """Serializes a ChartSpecification to a stable, indented JSON string."""

    def export(self, spec: ChartSpecification) -> str:
        """Return ``spec`` as an indented JSON string."""
        return spec.model_dump_json(indent=2)
