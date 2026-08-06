"""External context models: what one search query retrieves and how it's summarized.

Provider-independent — a real (or MCP-backed) ``BrowserProvider``
produces the exact same shapes a ``MockBrowserProvider`` does today, so
nothing above ``BrowserService`` ever needs to change when the provider
does.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class SourceResult(BaseModel):
    """One retrieved external source: a page/document found for a query.

    Deliberately thin — a title, a URL, and a snippet. This is metadata
    about a source, never the analyzed content of a ``BusinessDataset``.
    """

    query: str
    url: str
    title: str
    snippet: str
    provider: str
    retrieved_at: datetime


class SearchOutcome(BaseModel):
    """Everything BrowserService produced for one query: what it found, and a summary of it."""

    query: str
    sources: list[SourceResult] = Field(default_factory=list)
    summary: str
