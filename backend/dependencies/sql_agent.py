"""SQLAgent providers: SQLAgent, SQLAgentService.

Deliberately no provider for a separate result store here:
``get_sql_agent_service`` depends on ``get_agent_execution_result_store``
from ``backend.dependencies.file_agent`` — the same cached singleton
``FileAgentService`` uses — so one execution result is fetchable the
same way regardless of which agent produced it.
"""

from fastapi import Depends

from backend.agents.file.services.execution_result_store import (
    AgentExecutionResultStore,
)
from backend.agents.sql.execution.sql_agent import SQLAgent
from backend.agents.sql.services.sql_agent_service import SQLAgentService
from backend.dependencies.file_agent import get_agent_execution_result_store
from backend.dependencies.ingestion import get_business_dataset_store
from backend.dependencies.memory import get_memory_service
from backend.dependencies.tools import (
    get_analyze_dataset_tool,
    get_clean_dataset_tool,
    get_generate_report_tool,
    get_generate_visualization_tool,
    get_query_database_tool,
)
from backend.ingestion.registry.dataset_store import BusinessDatasetStore
from backend.memory.services.memory_service import MemoryService
from backend.tools.execution.analyze_dataset_tool import AnalyzeDatasetTool
from backend.tools.execution.clean_dataset_tool import CleanDatasetTool
from backend.tools.execution.generate_report_tool import GenerateReportTool
from backend.tools.execution.generate_visualization_tool import (
    GenerateVisualizationTool,
)
from backend.tools.execution.query_database_tool import QueryDatabaseTool


def get_sql_agent(
    query_database_tool: QueryDatabaseTool = Depends(get_query_database_tool),
    clean_dataset_tool: CleanDatasetTool = Depends(get_clean_dataset_tool),
    analyze_dataset_tool: AnalyzeDatasetTool = Depends(get_analyze_dataset_tool),
    generate_visualization_tool: GenerateVisualizationTool = Depends(get_generate_visualization_tool),
    generate_report_tool: GenerateReportTool = Depends(get_generate_report_tool),
    dataset_store: BusinessDatasetStore = Depends(get_business_dataset_store),
) -> SQLAgent:
    """Provide SQLAgent — orchestrates tools, never a business-logic implementation itself."""
    return SQLAgent(
        query_database_tool,
        clean_dataset_tool,
        analyze_dataset_tool,
        generate_visualization_tool,
        generate_report_tool,
        dataset_store,
    )


def get_sql_agent_service(
    agent: SQLAgent = Depends(get_sql_agent),
    result_store: AgentExecutionResultStore = Depends(get_agent_execution_result_store),
    memory_service: MemoryService = Depends(get_memory_service),
) -> SQLAgentService:
    """Provide SQLAgentService — the only object that should be used to run SQLAgent or fetch its results.

    Not itself cached (like ``get_file_agent_service``/``get_report_service``):
    SQLAgentService holds no state of its own — the one thing that must
    persist across callers is the shared ``AgentExecutionResultStore``'s
    contents, and that store is already the cached singleton.
    """
    return SQLAgentService(agent, result_store, memory_service)
