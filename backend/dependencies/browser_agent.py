"""BrowserAgent providers: result store, BrowserAgent, BrowserAgentService.

``get_browser_agent_result_store`` is cached like
``get_agent_execution_result_store`` (File/SQLAgent's own store) — but
it is a separate store, not shared with File/SQLAgent, since
``BrowserAgentResult`` is a genuinely different shape.
"""

from functools import lru_cache

from fastapi import Depends

from backend.agents.browser.execution.browser_agent import BrowserAgent
from backend.agents.browser.services.browser_agent_service import BrowserAgentService
from backend.agents.browser.services.execution_result_store import (
    BrowserAgentResultStore,
)
from backend.dependencies.memory import get_memory_service
from backend.dependencies.tools import get_search_web_tool
from backend.memory.services.memory_service import MemoryService
from backend.tools.execution.search_web_tool import SearchWebTool


@lru_cache
def get_browser_agent_result_store() -> BrowserAgentResultStore:
    """Return the process-wide BrowserAgentResultStore singleton.

    Cached for the same reason as ``get_agent_execution_result_store``:
    a result produced by one request (or one graph run) must still be
    fetchable ("Get execution result") in a later one.
    """
    return BrowserAgentResultStore()


def get_browser_agent(search_web_tool: SearchWebTool = Depends(get_search_web_tool)) -> BrowserAgent:
    """Provide BrowserAgent — orchestrates SearchWebTool, never a search/summarization implementation itself."""
    return BrowserAgent(search_web_tool)


def get_browser_agent_service(
    agent: BrowserAgent = Depends(get_browser_agent),
    result_store: BrowserAgentResultStore = Depends(get_browser_agent_result_store),
    memory_service: MemoryService = Depends(get_memory_service),
) -> BrowserAgentService:
    """Provide BrowserAgentService — the only object that should be used to run BrowserAgent or fetch its results."""
    return BrowserAgentService(agent, result_store, memory_service)
