"""CollaborationStore: the only place a CollaborationTask/message/delegation/
negotiation/result actually lives.

Mirrors ``ExecutionCheckpointStore``/``MemoryStore`` exactly: plain
in-memory dicts, keyed by ``collaboration_id``, holding immutable
snapshots — every write replaces a value wholesale, never mutates one
in place. Nothing outside ``backend/collaboration/`` should import this
directly; ``CollaborationService`` is the only public entry point.
"""

from collections import defaultdict

from backend.collaboration.models.artifact_exchange import ArtifactExchange
from backend.collaboration.models.collaboration_message import AgentMessage
from backend.collaboration.models.collaboration_result import CollaborationResult
from backend.collaboration.models.collaboration_task import CollaborationTask
from backend.collaboration.models.delegation import Delegation
from backend.collaboration.models.negotiation import NegotiationDecision


class CollaborationStore:
    """In-memory store for every collaboration session's task graph, messages, and history."""

    def __init__(self) -> None:
        self._tasks: dict[str, CollaborationTask] = {}
        self._messages: dict[str, list[AgentMessage]] = defaultdict(list)
        self._delegations: dict[str, list[Delegation]] = defaultdict(list)
        self._negotiations: dict[str, list[NegotiationDecision]] = defaultdict(list)
        self._exchanges: dict[str, list[ArtifactExchange]] = defaultdict(list)
        self._results: dict[str, CollaborationResult] = {}

    # -- Task -----------------------------------------------------------------

    def put_task(self, task: CollaborationTask) -> None:
        self._tasks[task.collaboration_id] = task

    def get_task(self, collaboration_id: str) -> CollaborationTask | None:
        return self._tasks.get(collaboration_id)

    def list_tasks(self) -> list[CollaborationTask]:
        return list(self._tasks.values())

    # -- Messages ---------------------------------------------------------------

    def add_message(self, message: AgentMessage) -> None:
        self._messages[message.collaboration_id].append(message)

    def list_messages(self, collaboration_id: str) -> list[AgentMessage]:
        return list(self._messages.get(collaboration_id, []))

    # -- Delegations --------------------------------------------------------------

    def add_delegation(self, delegation: Delegation) -> None:
        self._delegations[delegation.collaboration_id].append(delegation)

    def list_delegations(self, collaboration_id: str) -> list[Delegation]:
        return list(self._delegations.get(collaboration_id, []))

    # -- Negotiations ------------------------------------------------------------

    def add_negotiation(self, decision: NegotiationDecision) -> None:
        self._negotiations[decision.collaboration_id].append(decision)

    def list_negotiations(self, collaboration_id: str) -> list[NegotiationDecision]:
        return list(self._negotiations.get(collaboration_id, []))

    # -- Artifact exchanges -------------------------------------------------------

    def add_exchange(self, exchange: ArtifactExchange) -> None:
        self._exchanges[exchange.collaboration_id].append(exchange)

    def list_exchanges(self, collaboration_id: str) -> list[ArtifactExchange]:
        return list(self._exchanges.get(collaboration_id, []))

    # -- Results ------------------------------------------------------------------

    def put_result(self, result: CollaborationResult) -> None:
        self._results[result.collaboration_id] = result

    def get_result(self, collaboration_id: str) -> CollaborationResult | None:
        return self._results.get(collaboration_id)

    def clear(self) -> None:
        self._tasks.clear()
        self._messages.clear()
        self._delegations.clear()
        self._negotiations.clear()
        self._results.clear()
