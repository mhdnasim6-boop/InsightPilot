"""Session business logic: creation, retrieval, and activity tracking."""

from backend.core.exceptions import NotFoundError
from backend.models.session import Session
from backend.repositories.session_repository import SessionRepository
from backend.utils.ids import generate_id
from backend.utils.time import utc_now


class SessionService:
    """Creates and manages lightweight, unauthenticated sessions."""

    def __init__(self, session_repository: SessionRepository) -> None:
        self._repository = session_repository

    def create_session(self) -> Session:
        """Create and persist a new session with a fresh ID."""
        now = utc_now()
        session = Session(session_id=generate_id(), created_at=now, last_activity=now)
        return self._repository.add(session)

    def get_session(self, session_id: str) -> Session:
        """Fetch a session, raising NotFoundError if it doesn't exist."""
        session = self._repository.get(session_id)
        if session is None:
            raise NotFoundError(f"Session '{session_id}' was not found.")
        return session

    def touch_session(self, session_id: str) -> Session:
        """Update a session's last-activity timestamp to now."""
        session = self.get_session(session_id)
        session.last_activity = utc_now()
        return self._repository.update(session)

    def attach_file(self, session_id: str, file_id: str) -> Session:
        """Record that a file now belongs to a session."""
        session = self.get_session(session_id)
        session.uploaded_files.append(file_id)
        return self._repository.update(session)
