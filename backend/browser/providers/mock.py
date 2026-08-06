"""Deterministic, network-free provider for tests and local development.

Mirrors ``backend.ai.providers.mock.MockProvider`` exactly: the default
provider until a real (or Browser MCP-backed) one exists, and the
reference implementation any real provider must also satisfy.
"""

from backend.browser.models.context import SourceResult
from backend.browser.providers.base import BrowserProvider
from backend.utils.time import utc_now

_RESULTS_PER_QUERY = 3


class MockBrowserProvider(BrowserProvider):
    """Fabricates a fixed, deterministic set of sources for any query — no network calls."""

    provider_name = "mock"

    async def search(self, query: str) -> list[SourceResult]:
        """Return a deterministic, fixed-size list of sources derived from the query text."""
        retrieved_at = utc_now()
        slug = "-".join(query.strip().lower().split()) or "query"
        return [
            SourceResult(
                query=query,
                url=f"https://mock-search.local/{slug}/{index}",
                title=f"About '{query}' — result {index}",
                snippet=f"A deterministic mock snippet about '{query}' (result #{index}).",
                provider=self.provider_name,
                retrieved_at=retrieved_at,
            )
            for index in range(1, _RESULTS_PER_QUERY + 1)
        ]

    async def summarize(self, query: str, sources: list[SourceResult]) -> str:
        """Return a deterministic summary sentence derived from the retrieved sources."""
        if not sources:
            return f"No external sources were found for '{query}'."
        return f"Found {len(sources)} mock source(s) about '{query}': " + "; ".join(
            source.title for source in sources
        )
