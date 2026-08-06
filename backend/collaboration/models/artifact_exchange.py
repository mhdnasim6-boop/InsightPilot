"""ArtifactExchange: a record of one producer subtask's artifact fields being
routed into one dependent subtask's inputs.

Never a copy of the artifact itself (see ``ArtifactRouter``'s own
docstring for why) — just an audit entry: who produced it, who consumed
it, and which conventional keys were actually filled in.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ArtifactExchange(BaseModel):
    """One producer -> consumer artifact hand-off, recorded for audit/observability."""

    model_config = ConfigDict(frozen=True)

    exchange_id: str
    collaboration_id: str
    producer_subtask_id: str
    consumer_subtask_id: str
    artifact_keys: list[str] = Field(default_factory=list)
    created_at: datetime
