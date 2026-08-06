"""ExecutiveSummaryAgent providers: result store, ExecutiveSummaryAgent, ExecutiveSummaryService.

``get_executive_summary_agent`` now wires only ``GenerateExecutiveSummaryTool``
(Tool Layer, Phase 22) — the tool's own provider
(``backend.dependencies.tools.get_generate_executive_summary_tool``)
still shares the same cached ``PromptManager`` singleton Planner/Chat
use. ``get_executive_summary_result_store`` is cached like every other
agent's store, but is its own, separate store — independent from
File/SQL/Browser/Report's, per Phase 20's explicit requirement.
"""

from functools import lru_cache

from fastapi import Depends

from backend.agents.executive_summary.execution.executive_summary_agent import (
    ExecutiveSummaryAgent,
)
from backend.agents.executive_summary.services.execution_result_store import (
    ExecutiveSummaryResultStore,
)
from backend.agents.executive_summary.services.executive_summary_service import (
    ExecutiveSummaryService,
)
from backend.dependencies.memory import get_memory_service
from backend.dependencies.tools import get_generate_executive_summary_tool
from backend.memory.services.memory_service import MemoryService
from backend.tools.execution.generate_executive_summary_tool import (
    GenerateExecutiveSummaryTool,
)


@lru_cache
def get_executive_summary_result_store() -> ExecutiveSummaryResultStore:
    """Return the process-wide ExecutiveSummaryResultStore singleton.

    Cached for the same reason as every other agent's own store: a
    result produced by one request (or one graph run) must still be
    fetchable ("Get execution result") in a later one.
    """
    return ExecutiveSummaryResultStore()


def get_executive_summary_agent(
    generate_executive_summary_tool: GenerateExecutiveSummaryTool = Depends(get_generate_executive_summary_tool),
) -> ExecutiveSummaryAgent:
    """Provide ExecutiveSummaryAgent — calls GenerateExecutiveSummaryTool exactly once, nothing else."""
    return ExecutiveSummaryAgent(generate_executive_summary_tool)


def get_executive_summary_service(
    agent: ExecutiveSummaryAgent = Depends(get_executive_summary_agent),
    result_store: ExecutiveSummaryResultStore = Depends(get_executive_summary_result_store),
    memory_service: MemoryService = Depends(get_memory_service),
) -> ExecutiveSummaryService:
    """Provide ExecutiveSummaryService — the only object that should be used to run
    ExecutiveSummaryAgent or fetch its results."""
    return ExecutiveSummaryService(agent, result_store, memory_service)
