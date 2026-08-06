"""JSON export for an ExecutionTrace.

Trivial by design, mirroring ``backend.reporting.exporters.json_exporter``:
``ExecutionTrace`` is already a plain, self-contained Pydantic model —
exporting it to JSON is just serialization.
"""

from backend.observability.models.execution_trace import ExecutionTrace


class JSONTraceExporter:
    """Serializes an ExecutionTrace to a stable, indented JSON string."""

    def export(self, trace: ExecutionTrace) -> str:
        """Return ``trace`` as an indented JSON string."""
        return trace.model_dump_json(indent=2)
