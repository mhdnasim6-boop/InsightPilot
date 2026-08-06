"""File path and filename helpers.

Metadata-only: these functions compute where a file's bytes *would* live
and what its *safe* name would be. Nothing here reads or writes file
content — that arrives in a later phase.
"""

import re
from pathlib import Path

from backend.core.constants import MAX_FILENAME_LENGTH, UPLOADS_DIR
from backend.core.exceptions import StorageError

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe version of a user-supplied filename.

    Strips any directory components (defends against path traversal such
    as ``../../etc/passwd``) and replaces unsafe characters, falling back
    to a generic name if nothing safe remains.
    """
    name = Path(filename).name
    name = _UNSAFE_CHARS.sub("_", name).strip("._")
    return name[:MAX_FILENAME_LENGTH] or "unnamed_file"


def build_upload_path(session_id: str, file_id: str, original_filename: str) -> Path:
    """Compute the on-disk path for an uploaded file's metadata record.

    Files are namespaced as ``data/uploads/<session_id>/<file_id>_<safe_name>``
    so per-session lookups and cleanup are simple later.
    """
    safe_name = sanitize_filename(original_filename)
    path = UPLOADS_DIR / session_id / f"{file_id}_{safe_name}"

    resolved_uploads_dir = UPLOADS_DIR.resolve()
    resolved_path = path.resolve()
    if resolved_uploads_dir not in resolved_path.parents:
        raise StorageError(f"Computed upload path escapes the uploads directory: {resolved_path}")

    return path
