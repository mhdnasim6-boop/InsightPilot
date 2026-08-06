"""JSON export for one ReflectionResult.

Trivial by design, mirroring ``backend.memory.exporters.json_exporter``:
``ReflectionResult`` is already a plain, self-contained Pydantic model —
exporting it to JSON is just serialization.
"""

import json

from backend.reflection.models.reflection_result import ReflectionResult


class JSONReflectionExporter:
    """Serializes one ReflectionResult to a stable, indented JSON string."""

    def export(self, result: ReflectionResult) -> str:
        """Return ``result`` as an indented JSON string."""
        return json.dumps(result.model_dump(mode="json"), indent=2)
