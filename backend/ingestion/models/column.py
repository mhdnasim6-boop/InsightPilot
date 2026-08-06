"""Per-column descriptive metadata."""

from pydantic import BaseModel


class ColumnMetadata(BaseModel):
    """Facts about a single column, extracted — never inferred or cleaned."""

    name: str
    dtype: str
    non_null_count: int
    null_count: int
    unique_count: int
