"""ArtifactRouter: makes one agent's output automatically available to a dependent agent.

Never duplicates ``BusinessDataset``/``ReportDocument``/``AnalysisResult``/
``VisualizationResult``/etc. — a producer subtask's result is already a
JSON-shaped dict by the time it lands in ``StepExecutionState.result``
(``DAGScheduler`` stores ``result.model_dump(mode="json")``), and every
consumer agent's own input validator (``ReportAgent``'s
``validate_agent_input``, ``ExecutiveSummaryAgent``'s own validator)
already expects its inputs as JSON-shaped dicts under a conventional key
(``dataset``, ``cleaning_outcome``, ``analysis_result``,
``visualization_result``, ``browser_agent_result``, ``report_document``).
This module only knows that convention — it never re-parses or
re-validates the artifacts themselves.
"""

from typing import Any

# (producer node_name) -> [(result field name, dependent input key)].
# `None` as the field name means "pass the producer's whole result object."
_ARTIFACT_FIELD_MAP: dict[str, list[tuple[str | None, str]]] = {
    "file_agent": [
        ("dataset", "dataset"),
        ("cleaning", "cleaning_outcome"),
        ("analysis", "analysis_result"),
        ("visualization", "visualization_result"),
    ],
    "sql_agent": [
        ("dataset", "dataset"),
        ("cleaning", "cleaning_outcome"),
        ("analysis", "analysis_result"),
        ("visualization", "visualization_result"),
    ],
    "browser_agent": [(None, "browser_agent_result")],
    "report_agent": [("report_document", "report_document")],
}


class ArtifactRouter:
    """Merges a producer subtask's known result fields into a dependent subtask's inputs."""

    def route(
        self, producer_node_name: str, producer_result: dict[str, Any], dependent_inputs: dict[str, Any]
    ) -> tuple[dict[str, Any], list[str]]:
        """Return (``dependent_inputs`` plus whatever ``producer_result`` routes to it, filled keys).

        Only fields the dependent hasn't already declared explicitly are
        filled in — an explicit input always wins over a routed one.
        """
        routed = dict(dependent_inputs)
        filled: list[str] = []
        for field_name, target_key in _ARTIFACT_FIELD_MAP.get(producer_node_name, []):
            if target_key in routed:
                continue
            value = producer_result if field_name is None else producer_result.get(field_name)
            if value is not None:
                routed[target_key] = value
                filled.append(target_key)
        return routed, filled

    def route_all(
        self, producers: dict[str, tuple[str, dict[str, Any]]], dependent_inputs: dict[str, Any], dependencies: list[str]
    ) -> tuple[dict[str, Any], dict[str, list[str]]]:
        """Route every declared dependency's artifacts, in dependency order, into one inputs dict.

        ``producers`` maps subtask_id -> (node_name, result_dict) for
        every already-completed subtask available this collaboration.
        Returns (merged inputs, {producer_subtask_id: filled_keys}) — the
        second value is what ``CollaborationCoordinator`` records as
        ``ArtifactExchange`` entries.
        """
        routed = dict(dependent_inputs)
        filled_by_producer: dict[str, list[str]] = {}
        for dependency_id in dependencies:
            producer = producers.get(dependency_id)
            if producer is None:
                continue
            node_name, result = producer
            routed, filled = self.route(node_name, result, routed)
            if filled:
                filled_by_producer[dependency_id] = filled
        return routed, filled_by_producer
