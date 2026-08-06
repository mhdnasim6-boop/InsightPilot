"""Repository providers.

Cached with ``lru_cache`` so each repository is a singleton for the life
of the process — in-memory storage would be pointless if a fresh, empty
instance were created on every request.
"""

from functools import lru_cache

from backend.repositories.file_repository import FileRepository, InMemoryFileRepository
from backend.repositories.session_repository import (
    InMemorySessionRepository,
    SessionRepository,
)


@lru_cache
def get_session_repository() -> SessionRepository:
    """Return the process-wide session repository singleton."""
    return InMemorySessionRepository()


@lru_cache
def get_file_repository() -> FileRepository:
    """Return the process-wide file-metadata repository singleton."""
    return InMemoryFileRepository()
