"""Validates a FileAgent invocation's own inputs before any service is called.

Deliberately shallow: this never re-validates a file's contents (that's
``DatasetValidator``'s job, already reused via ``IngestionService``) — it
only checks that the caller gave FileAgent enough to even attempt a run.
"""

from backend.agents.file.exceptions.errors import InvalidAgentInputError
from backend.planning.models.step import ExecutionStep


def validate_agent_input(step: ExecutionStep, session_id: str | None) -> str:
    """Check that ``step``/``session_id`` carry what FileAgent needs to run.

    Returns the validated ``dataset_reference`` for convenience (the one
    piece of data every caller immediately needs next). Raises
    ``InvalidAgentInputError`` if the session is missing or
    ``step.inputs`` has no usable ``dataset_reference``.
    """
    if not session_id or not session_id.strip():
        raise InvalidAgentInputError(f"FileAgent step '{step.step_id}' has no session_id.")

    dataset_reference = step.inputs.get("dataset_reference")
    if not isinstance(dataset_reference, str) or not dataset_reference.strip():
        raise InvalidAgentInputError(
            f"FileAgent step '{step.step_id}' is missing a non-empty 'dataset_reference' in step.inputs."
        )

    return dataset_reference
