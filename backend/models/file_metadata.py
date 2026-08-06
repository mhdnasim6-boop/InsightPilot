"""Uploaded file metadata domain model.

Metadata only — no file content, and nothing in this phase reads or
writes file bytes.
"""

from datetime import datetime

from pydantic import BaseModel


class FileMetadata(BaseModel):
    """Metadata describing a file that belongs to a session."""

    file_id: str
    session_id: str
    original_filename: str
    stored_filename: str
    storage_path: str
    content_type: str | None = None
    size_bytes: int | None = None
    uploaded_at: datetime
