"""JSON export for a list of MemoryItems.

Trivial by design, mirroring ``backend.observability.exporters.json_exporter``:
``MemoryItem`` is already a plain, self-contained Pydantic model —
exporting it to JSON is just serialization.
"""

import json

from backend.memory.models.memory_item import MemoryItem


class JSONMemoryExporter:
    """Serializes a list of MemoryItems to a stable, indented JSON array string."""

    def export(self, items: list[MemoryItem]) -> str:
        """Return ``items`` as an indented JSON array string."""
        return json.dumps([item.model_dump(mode="json") for item in items], indent=2)
