"""export_optimization_report_json: JSON export of a complete OptimizationReport."""

import json

from backend.autonomous.models.optimization_report import OptimizationReport


def export_optimization_report_json(report: OptimizationReport) -> str:
    """Serialize a complete OptimizationReport (profile, bottlenecks, actions, recommendations) as JSON."""
    return json.dumps(report.model_dump(mode="json"), indent=2)
