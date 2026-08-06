"""In-memory report_id -> ReportDocument store.

Mirrors ``backend.ingestion.registry.dataset_store.BusinessDatasetStore``
exactly. Added because ``ReportService.build_report()`` returns a
``ReportDocument`` to its caller but never persisted a registry of
"every report generated so far" itself — needed for "Get report" to have
anything to fetch later. Not in its own subfolder: this phase's CREATE
list didn't request a ``registry/`` package, so this is a flat module at
the reporting package's own root, the same way the Planner's exception
hierarchy is a flat ``exceptions.py`` rather than a package.
"""

from backend.reporting.models.report_document import ReportDocument


class ReportStore:
    """Process-wide store of generated reports, keyed by report ID."""

    def __init__(self) -> None:
        self._reports: dict[str, ReportDocument] = {}

    def put(self, document: ReportDocument) -> None:
        """Store (or overwrite) a report, keyed by its own ``report_id``."""
        self._reports[document.report_id] = document

    def get(self, report_id: str) -> ReportDocument | None:
        """Return the report for a report ID, or None if not present."""
        return self._reports.get(report_id)

    def list(self) -> list[ReportDocument]:
        """Return every stored report, most recently added first."""
        return list(reversed(self._reports.values()))

    def delete(self, report_id: str) -> bool:
        """Remove a stored report. Returns True if it existed."""
        return self._reports.pop(report_id, None) is not None
