"""Uploaded file metadata repository: abstract contract + in-memory implementation."""

from abc import abstractmethod

from backend.models.file_metadata import FileMetadata
from backend.repositories.base import BaseRepository


class FileRepository(BaseRepository[FileMetadata, str]):
    """File-metadata-specific repository contract."""

    @abstractmethod
    def list_by_session(self, session_id: str) -> list[FileMetadata]:
        """Return all file metadata belonging to a given session."""


class InMemoryFileRepository(FileRepository):
    """In-memory file-metadata store, keyed by file ID."""

    def __init__(self) -> None:
        self._files: dict[str, FileMetadata] = {}

    def add(self, entity: FileMetadata) -> FileMetadata:
        self._files[entity.file_id] = entity
        return entity

    def get(self, entity_id: str) -> FileMetadata | None:
        return self._files.get(entity_id)

    def update(self, entity: FileMetadata) -> FileMetadata:
        self._files[entity.file_id] = entity
        return entity

    def delete(self, entity_id: str) -> bool:
        return self._files.pop(entity_id, None) is not None

    def list_by_session(self, session_id: str) -> list[FileMetadata]:
        return [f for f in self._files.values() if f.session_id == session_id]

    def list(self) -> list[FileMetadata]:
        return list(self._files.values())
