"""Abstract provider interface every external-search backend must implement.

This is the one seam between InsightPilot and any real search/browsing
backend. ``BrowserService`` today, ``BrowserAgent`` tomorrow through it,
depend only on this interface and the provider-independent models in
``backend.browser.models`` — no provider-specific type ever crosses it.
A future Browser MCP server plugs in as a new ``BrowserProvider``
implementation, exactly the way a real ``AIProvider`` would replace
``MockProvider`` in ``backend.ai``.
"""

from abc import ABC, abstractmethod

from backend.browser.models.context import SourceResult


class BrowserProvider(ABC):
    """Contract every browser/search backend (mock or real) must satisfy."""

    provider_name: str

    @abstractmethod
    async def search(self, query: str) -> list[SourceResult]:
        """Search and retrieve source metadata (title/url/snippet) for one query."""

    @abstractmethod
    async def summarize(self, query: str, sources: list[SourceResult]) -> str:
        """Summarize a query's retrieved sources into one piece of external context."""
