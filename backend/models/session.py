"""Session domain model."""

from datetime import datetime

from pydantic import BaseModel, Field


class Session(BaseModel):
    """A lightweight, unauthenticated user session.

    Tracks identity, activity timestamps, and which uploaded files belong
    to it. No authentication in this phase — a session is just a handle
    future requests can be correlated against.
    """

    session_id: str
    created_at: datetime
    last_activity: datetime
    uploaded_files: list[str] = Field(default_factory=list)
