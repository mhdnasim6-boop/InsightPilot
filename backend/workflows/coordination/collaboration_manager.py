"""WorkflowCollaborationManager: thin wrapper over the existing
CollaborationService (Phase 30) — reused, never reimplemented, for
workflows whose steps need agent-to-agent delegation/artifact-passing
rather than a single linear/DAG plan.

Optional, exactly like every other optional collaborator in this
codebase (``ObservabilityService | None`` on a dozen services already):
a Workflow with no collaboration needs works with this collaborator
absent.
"""

from backend.collaboration.models.agent_capability import AgentCapability
from backend.collaboration.models.collaboration_request import CollaborationRequest
from backend.collaboration.models.collaboration_task import CollaborationTask
from backend.collaboration.services.collaboration_service import CollaborationService


class WorkflowCollaborationManager:
    """Delegates every real operation straight to CollaborationService."""

    def __init__(self, collaboration_service: CollaborationService | None = None) -> None:
        self._collaboration_service = collaboration_service

    @property
    def is_available(self) -> bool:
        return self._collaboration_service is not None

    def discover_capabilities(self) -> list[AgentCapability]:
        """Every dynamically discovered agent's capability — empty if no CollaborationService is wired."""
        if self._collaboration_service is None:
            return []
        return self._collaboration_service.discover_capabilities()

    def start_session(self, request: CollaborationRequest) -> CollaborationTask:
        """Start a real collaboration session for a workflow step that needs multi-agent delegation.
        Raises RuntimeError if no CollaborationService was wired — a workflow that never
        uses collaboration steps never needs one constructed."""
        if self._collaboration_service is None:
            raise RuntimeError("No CollaborationService is configured for this WorkflowCollaborationManager.")
        return self._collaboration_service.create_session(request)
