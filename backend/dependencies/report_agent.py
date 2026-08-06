"""ReportAgent providers: result store, ReportAgent, ReportAgentService.

``get_report_agent_result_store`` is cached like
``get_agent_execution_result_store``/``get_browser_agent_result_store``
— but it is its own, separate store, not shared with File/SQL/Browser's,
since ``ReportAgentResult`` is a genuinely different shape.
"""

from functools import lru_cache

from fastapi import Depends

from backend.agents.report.execution.report_agent import ReportAgent
from backend.agents.report.services.execution_result_store import (
    ReportAgentResultStore,
)
from backend.agents.report.services.report_agent_service import ReportAgentService
from backend.dependencies.tools import get_generate_report_tool
from backend.tools.execution.generate_report_tool import GenerateReportTool


@lru_cache
def get_report_agent_result_store() -> ReportAgentResultStore:
    """Return the process-wide ReportAgentResultStore singleton.

    Cached for the same reason as ``get_agent_execution_result_store``:
    a result produced by one request (or one graph run) must still be
    fetchable ("Get execution result") in a later one.
    """
    return ReportAgentResultStore()


def get_report_agent(generate_report_tool: GenerateReportTool = Depends(get_generate_report_tool)) -> ReportAgent:
    """Provide ReportAgent — orchestrates GenerateReportTool, never a reporting implementation itself."""
    return ReportAgent(generate_report_tool)


def get_report_agent_service(
    agent: ReportAgent = Depends(get_report_agent),
    result_store: ReportAgentResultStore = Depends(get_report_agent_result_store),
) -> ReportAgentService:
    """Provide ReportAgentService — the only object that should be used to run ReportAgent or fetch its results."""
    return ReportAgentService(agent, result_store)
