"""Session repository: abstract contract + in-memory implementation."""

from backend.models.session import Session
from backend.repositories.base import BaseRepository


class SessionRepository(BaseRepository[Session, str]):
    """Session-specific repository contract."""


class InMemorySessionRepository(SessionRepository):
    """In-memory session store, keyed by session ID.

    Swapping this for a SQL-backed implementation later means writing a
    new class that implements ``SessionRepository`` — nothing that
    depends on the abstract type needs to change.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def add(self, entity: Session) -> Session:
        self._sessions[entity.session_id] = entity
        return entity

    def get(self, entity_id: str) -> Session | None:
        return self._sessions.get(entity_id)

    def update(self, entity: Session) -> Session:
        self._sessions[entity.session_id] = entity
        return entity

    def delete(self, entity_id: str) -> bool:
        return self._sessions.pop(entity_id, None) is not None

    def list(self) -> list[Session]:
        return list(self._sessions.values())
