"""export_workflow_json: JSON export of a Workflow (+ its latest execution)."""

import json

from backend.workflows.models.workflow import Workflow
from backend.workflows.models.workflow_execution import WorkflowExecution


def export_workflow_json(workflow: Workflow, latest_execution: WorkflowExecution | None) -> str:
    """Serialize a workflow and its most recent execution (if any) as one JSON document."""
    payload = {
        "workflow": workflow.model_dump(mode="json"),
        "latest_execution": latest_execution.model_dump(mode="json") if latest_execution is not None else None,
    }
    return json.dumps(payload, indent=2)
