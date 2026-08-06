"""JSON export for one OptimizationResult — trivial by design, mirroring
``backend.reflection.exporters.json_exporter``.
"""

import json

from backend.adaptive.models.optimization_result import OptimizationResult


class JSONOptimizationExporter:
    """Serializes one OptimizationResult to a stable, indented JSON string."""

    def export(self, result: OptimizationResult) -> str:
        """Return ``result`` as an indented JSON string."""
        return json.dumps(result.model_dump(mode="json"), indent=2)
