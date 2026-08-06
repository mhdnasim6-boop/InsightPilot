"""External context retrieval.

The only object anything (BrowserAgent, a future ChatService citation
feature, ...) should use to search for external context — never a
``BrowserProvider`` directly. Swapping the default provider for a real
one (or a Browser MCP-backed one) never touches a caller of this
service, mirroring ``AIService``'s own relationship to ``AIProvider``.
"""

from backend.browser.models.context import SearchOutcome
from backend.browser.providers.base import BrowserProvider


class BrowserService:
    """Receives a query, resolves the configured provider, returns structured external context."""

    def __init__(self, provider: BrowserProvider) -> None:
        self._provider = provider

    async def search(self, query: str) -> SearchOutcome:
        """Search, retrieve, and summarize external context for one query."""
        sources = await self._provider.search(query)
        summary = await self._provider.summarize(query, sources)
        return SearchOutcome(query=query, sources=sources, summary=summary)
