"""CSV export for an ExecutionTrace: one row per timeline event.

Reuses ``build_timeline()`` (the same projection the Execution Timeline
REST endpoint and frontend view use) so the CSV export and the on-screen
timeline can never disagree about what happened, in what order.
"""

import csv
import io

from backend.observability.models.execution_trace import ExecutionTrace
from backend.observability.services.timeline import build_timeline

_FIELDNAMES = ["kind", "name", "start_time", "end_time", "duration_ms", "status"]


class CSVTraceExporter:
    """Renders an ExecutionTrace's timeline as CSV, one row per event."""

    def export(self, trace: ExecutionTrace) -> str:
        """Return ``trace``'s timeline as a CSV string, oldest event first."""
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=_FIELDNAMES)
        writer.writeheader()
        for entry in build_timeline(trace):
            writer.writerow(
                {
                    "kind": entry.kind,
                    "name": entry.name,
                    "start_time": entry.start_time.isoformat(),
                    "end_time": entry.end_time.isoformat() if entry.end_time else "",
                    "duration_ms": f"{entry.duration_ms:.2f}" if entry.duration_ms is not None else "",
                    "status": entry.status,
                }
            )
        return buffer.getvalue()
