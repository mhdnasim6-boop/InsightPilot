"""SearchWebTool: wraps BrowserService.search() — nothing else.

One query per call, matching BrowserService's own signature exactly —
BrowserAgent still loops over its own queries, calling this tool once
per query, exactly as it looped over ``BrowserService.search()`` before
this phase.
"""

from backend.browser.models.context import SearchOutcome
from backend.services.browser_service import BrowserService
from backend.tools.base.tool import Tool
from backend.tools.models.inputs import SearchWebInput


class SearchWebTool(Tool[SearchWebInput, SearchOutcome]):
    """Searches, retrieves, and summarizes external context for one query."""

    name = "search_web"
    description = "Search, retrieve, and summarize external context for one query."
    input_model = SearchWebInput
    output_model = SearchOutcome

    def __init__(self, browser_service: BrowserService) -> None:
        self._browser_service = browser_service

    async def execute(self, tool_input: SearchWebInput) -> SearchOutcome:
        return await self._browser_service.search(tool_input.query)
