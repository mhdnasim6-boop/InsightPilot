"""WorkerCapability: one node_name a worker advertises it can execute.

Deliberately a small, dedicated model (rather than a plain ``list[str]``
on ``Worker``) so a future capability can carry its own metadata (a
per-capability concurrency override, a version, ...) without a breaking
change to ``Worker`` itself — mirrors ``MemoryReference``'s own "small
dedicated model, not a bare string" precedent.
"""

from pydantic import BaseModel, ConfigDict


class WorkerCapability(BaseModel):
    """One node_name a worker can execute — validated against ``AgentCapabilityRegistry``."""

    model_config = ConfigDict(frozen=True)

    node_name: str
