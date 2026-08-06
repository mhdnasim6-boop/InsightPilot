"""File metadata business logic.

Registers metadata for uploaded files and keeps a session's file list in
sync. No file content is ever read or written here — that's out of scope
for this phase.
"""

from backend.core.exceptions import NotFoundError, ValidationError
from backend.models.file_metadata import FileMetadata
from backend.repositories.file_repository import FileRepository
from backend.services.session_service import SessionService
from backend.utils.files import build_upload_path
from backend.utils.ids import generate_id
from backend.utils.time import utc_now
from backend.utils.validators import is_supported_file_type


class FileService:
    """Manages uploaded file metadata and its association with a session."""

    def __init__(self, file_repository: FileRepository, session_service: SessionService) -> None:
        self._repository = file_repository
        self._session_service = session_service

    def register_file(
        self,
        session_id: str,
        original_filename: str,
        content_type: str | None = None,
        size_bytes: int | None = None,
    ) -> FileMetadata:
        """Register metadata for an uploaded file and attach it to its session.

        Validates the file type and that the session exists; does not
        read or store the file's bytes.
        """
        if not is_supported_file_type(original_filename):
            raise ValidationError(f"Unsupported file type: '{original_filename}'.")

        self._session_service.get_session(session_id)  # raises NotFoundError if missing

        file_id = generate_id()
        storage_path = build_upload_path(session_id, file_id, original_filename)

        metadata = FileMetadata(
            file_id=file_id,
            session_id=session_id,
            original_filename=original_filename,
            stored_filename=storage_path.name,
            storage_path=str(storage_path),
            content_type=content_type,
            size_bytes=size_bytes,
            uploaded_at=utc_now(),
        )
        self._repository.add(metadata)
        self._session_service.attach_file(session_id, file_id)
        return metadata

    def get_file(self, file_id: str) -> FileMetadata:
        """Fetch file metadata, raising NotFoundError if it doesn't exist."""
        metadata = self._repository.get(file_id)
        if metadata is None:
            raise NotFoundError(f"File '{file_id}' was not found.")
        return metadata

    def list_session_files(self, session_id: str) -> list[FileMetadata]:
        """Return all file metadata belonging to a session."""
        return self._repository.list_by_session(session_id)
