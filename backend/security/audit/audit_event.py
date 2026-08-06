"""AuditEvent: one recorded, authenticated request — the shape every
audit record takes, and what GET /audit returns.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEvent(BaseModel):
    """An immutable record of one authenticated request's outcome."""

    model_config = ConfigDict(frozen=True)

    audit_id: str
    timestamp: datetime
    user_id: str
    username: str
    action: str
    endpoint: str
    method: str
    duration_ms: float
    status_code: int
    success: bool
    request_id: str
