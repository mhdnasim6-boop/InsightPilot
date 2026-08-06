"""The central, universal representation of ingested data.

Every future agent (File, Cleaning, Analysis, Visualization, Report)
consumes a ``BusinessDataset`` — never a file path, a database
connection, or a pandas DataFrame directly. The real DataFrame (too
large/unserializable to embed as a field) lives in a
``backend.ingestion.registry.dataframe_store.DataFrameStore``, keyed by
``dataframe_reference``; agents that need the full data resolve it there
instead of re-reading the source.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.ingestion.models.column import ColumnMetadata
from backend.ingestion.models.source_type import SourceType


class BusinessDataset(BaseModel):
    """A standardized description of one ingested dataset.

    Not treated as immutable like ``ExecutionPlan``: future agents
    (cleaning, schema-linking) are expected to progressively enrich a
    dataset's ``quality_summary``/``relationships`` over its lifetime, the
    same way ``InsightPilotState`` accumulates fields across a run.
    """

    dataset_id: str
    dataset_name: str
    source_type: SourceType
    source_location: str
    # Field name "schema" is requested by name in this model's spec. It
    # shadows BaseModel's deprecated `schema()` classmethod, which mypy
    # sees as a real incompatible-override; the runtime behavior is
    # correct (verified: constructs and round-trips through
    # model_dump_json() cleanly), so the mismatch is with mypy's view of
    # a deprecated pydantic v1 method, not with this field.
    schema: dict[str, str] = Field(default_factory=dict)  # type: ignore[assignment]
    columns: list[ColumnMetadata] = Field(default_factory=list)
    row_count: int
    column_count: int
    file_size: int | None = None
    created_at: datetime
    loaded_at: datetime
    dataframe_reference: str | None = None
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
    quality_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    relationships: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    description: str | None = None
