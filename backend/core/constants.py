"""Single location for project-wide constants: default folders, supported
file types, and other application-level values. Nothing outside this file
should hardcode these.
"""

from shared.paths import PROJECT_ROOT

# Default folders
DATA_DIR = PROJECT_ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"

# Supported uploaded file types (extensions, lowercase, including the dot).
# Matches the file types named in the project's architecture: Excel, CSV,
# PDF, Word, and PowerPoint.
SUPPORTED_FILE_TYPES: frozenset[str] = frozenset(
    {".csv", ".xlsx", ".xls", ".pdf", ".docx", ".pptx"}
)

# Safety limit for generated/sanitized filenames.
MAX_FILENAME_LENGTH = 255
