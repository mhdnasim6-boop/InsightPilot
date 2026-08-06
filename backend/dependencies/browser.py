"""Browser infrastructure providers: provider, BrowserService.

Mirrors ``backend.dependencies.ai``: today the only ``BrowserProvider``
is the deterministic ``MockBrowserProvider`` — a real (or Browser
MCP-backed) provider swaps in here later with no change to any caller
of ``get_browser_service``.
"""

from functools import lru_cache

from fastapi import Depends

from backend.browser.providers.base import BrowserProvider
from backend.browser.providers.mock import MockBrowserProvider
from backend.services.browser_service import BrowserService


@lru_cache
def get_browser_provider() -> BrowserProvider:
    """Return the process-wide BrowserProvider singleton — today, always the mock provider."""
    return MockBrowserProvider()


def get_browser_service(provider: BrowserProvider = Depends(get_browser_provider)) -> BrowserService:
    """Provide the BrowserService — the only object that should be used for external search."""
    return BrowserService(provider)
